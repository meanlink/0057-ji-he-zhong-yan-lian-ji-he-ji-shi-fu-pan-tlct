"""Process one committed task at a time, atomically with its domain changes."""
import logging
import time
from pathlib import Path

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from psycopg.types.json import Jsonb

import domain
from core import CACHE, db

HEARTBEAT = Path("/tmp/yangyang-worker-heartbeat")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("worker")


def _mark_correction_failed(connection, payload, detail):
    """任务事务回滚后，在独立事务里把在途更正单置为 failed，使其可重试。"""
    correction_id = payload.get("correction_id") if isinstance(payload, dict) else None
    if not correction_id or correction_id < 0:
        return
    try:
        with connection.transaction():
            connection.execute(
                """UPDATE muster_corrections
                   SET status='failed', detail=%s, updated_at=now()
                   WHERE id=%s AND status IN ('queued','running')""",
                (detail, correction_id),
            )
    except Exception:
        log.exception("Could not mark correction %s as failed", correction_id)


def process(connection):
    job = connection.execute("""
        SELECT id,kind,payload FROM app_jobs
        WHERE status='queued' AND available_at <= now()
        ORDER BY available_at,id FOR UPDATE SKIP LOCKED LIMIT 1
    """).fetchone()
    if job is None:
        return False
    try:
        with connection.transaction():
            connection.execute("UPDATE app_jobs SET status='running' WHERE id=%s", (job["id"],))
            result = domain.run_job(connection, job["kind"], job["payload"])
            connection.execute(
                "UPDATE app_jobs SET status='done',result=%s,finished_at=now() WHERE id=%s",
                (Jsonb(jsonable_encoder(result)), job["id"]),
            )
        log.info("Completed job %s (%s)", job["id"], job["kind"])
    except Exception as exc:
        log.exception("Job %s failed", job["id"])
        detail = str(exc.detail) if isinstance(exc, HTTPException) else "后台计算失败，请核对输入后重试"
        with connection.transaction():
            connection.execute(
                "UPDATE app_jobs SET status='failed',error=%s,finished_at=now() WHERE id=%s",
                (detail, job["id"]),
            )
        _mark_correction_failed(connection, job["payload"], detail)
    return True


if __name__ == "__main__":
    while True:
        try:
            CACHE.ping()
            with db() as connection:
                touched = process(connection)
            HEARTBEAT.touch()
            if not touched:
                time.sleep(.5)
        except Exception:
            log.exception("Worker waiting for dependencies")
            time.sleep(2)
