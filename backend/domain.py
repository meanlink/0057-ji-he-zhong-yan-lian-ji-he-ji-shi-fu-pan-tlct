from fastapi import APIRouter
from roster_routes import router as router_0
from clock_routes import router as router_1
from tail_routes import router as router_2
from followup_routes import router as router_3
from correction_routes import router as router_4
from muster_seed import seed
import tail_worker
import correction_worker

router = APIRouter(prefix="/api")
router.include_router(router_0)
router.include_router(router_1)
router.include_router(router_2)
router.include_router(router_3)
router.include_router(router_4)

_JOBS = {
    "estimate_muster_tail": tail_worker.run,
    "correct_muster_tail": correction_worker.run,
}


def run_job(cx, kind, data):
    try:
        return _JOBS[kind](cx, kind, data)
    except KeyError as exc:
        raise ValueError(kind) from exc
