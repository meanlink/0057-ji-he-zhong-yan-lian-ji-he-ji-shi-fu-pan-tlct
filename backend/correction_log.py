"""更正单的开立、查询与重试；重算本体在 correction_worker 中。"""
from fastapi import HTTPException
from psycopg.types.json import Jsonb

from core import enqueue
from drill_registry import drill, roster
from tail_persist import read as read_tail

IN_FLIGHT = ("queued", "running")
# 只有这两种状态允许对同一张单重新入队。
RETRIABLE = ("failed", "returned")


def validate_observations(window, roster, observations):
    """纯函数校验更正后的整套窗内签到原件，与 clock_log 的窗口规则保持一致。"""
    by_code = {item.code: item for item in observations}
    if len(by_code) != len(observations):
        raise HTTPException(409, "更正清单中存在重复记录码")
    members = {row["code"]: row for row in roster}
    unknown = sorted(set(by_code) - set(members))
    if unknown:
        raise HTTPException(409, f"记录码不在本轮名册：{', '.join(unknown)}")
    missing = sorted(set(members) - set(by_code))
    if missing:
        raise HTTPException(409, f"更正清单缺少 {len(missing)} 位的窗内签到原件：{', '.join(missing)}")
    cutoff = window["cutoff"]
    for item in observations:
        if item.seconds > cutoff:
            raise HTTPException(409, f"{item.code} 的时间超过观察窗 {cutoff} 秒")
        if item.kind == "censored" and item.seconds != cutoff:
            raise HTTPException(409, f"{item.code} 的右删失记录只能使用观察窗截止时刻 {cutoff} 秒")
    return [item.model_dump() for item in observations]


def blocking_followups(cx, drill_code, observations):
    """补查单绑定到截止未签到的原件；更正会使该原件不再是删失记录时构成阻断。"""
    corrected = {item["code"]: item["kind"] for item in observations}
    rows = cx.execute(
        "SELECT code FROM muster_followup WHERE drill=%s ORDER BY code", (drill_code,)
    ).fetchall()
    return [row["code"] for row in rows if corrected.get(row["code"]) != "censored"]


def list_corrections(cx, drill_code):
    drill(cx, drill_code)
    return cx.execute(
        """SELECT c.id,c.drill,c.owner,c.reason,c.status,c.detail,
                  c.job_id,c.created_at,c.updated_at,j.status AS job_state,j.error AS job_error
           FROM muster_corrections c JOIN app_jobs j ON j.id=c.job_id
           WHERE c.drill=%s ORDER BY c.id""",
        (drill_code,),
    ).fetchall()


def open_correction(cx, drill_code, body, owner):
    # 对演练行加锁，与封存、开补查、重试互斥，保证状态判断在同一事务内有效。
    window = drill(cx, drill_code, True)
    if window["status"] != "calculated":
        raise HTTPException(409, "曲线发布后才能发起更正")
    active = cx.execute(
        "SELECT id FROM muster_corrections WHERE drill=%s AND status = ANY(%s) FOR UPDATE",
        (drill_code, list(IN_FLIGHT)),
    ).fetchone()
    if active:
        raise HTTPException(409, "该观察窗已有在途更正单，请等待处理结束")
    observations = validate_observations(window, roster(cx, drill_code), body.observations)
    # 冻结当前曲线与窗内原件，重算期间任何查询仍看到这份基线。
    baseline = read_tail(cx, drill_code)
    baseline["clock"] = cx.execute(
        "SELECT code,seconds,kind FROM muster_clock WHERE drill=%s ORDER BY code",
        (drill_code,),
    ).fetchall()
    job_id = enqueue(cx, "correct_muster_tail",
                     {"drill": drill_code, "correction_id": -1})
    row = cx.execute(
        """INSERT INTO muster_corrections(drill,owner,reason,observations,baseline,job_id)
           VALUES (%s,%s,%s,%s,%s,%s) RETURNING *""",
        (drill_code, owner, body.reason, Jsonb(observations), Jsonb(baseline), job_id),
    ).fetchone()
    # 回填 payload，让 worker 能直接定位这张单；job 与更正单在同一事务提交。
    cx.execute("UPDATE app_jobs SET payload=%s WHERE id=%s",
               (Jsonb({"drill": drill_code, "correction_id": row["id"]}), job_id))
    return {"ticket": row, "job_id": job_id}


def retry_correction(cx, drill_code, ticket_id):
    drill(cx, drill_code, True)
    ticket = cx.execute(
        "SELECT * FROM muster_corrections WHERE id=%s AND drill=%s FOR UPDATE",
        (ticket_id, drill_code),
    ).fetchone()
    if ticket is None:
        raise HTTPException(404, "没有这张更正单")
    if ticket["status"] not in RETRIABLE:
        if ticket["status"] == "effective":
            # 已生效的更正绝不重复发布。
            raise HTTPException(409, "更正已生效，无需重试，当前曲线即为更正后曲线")
        raise HTTPException(409, "更正单仍在处理中，不能重复发起")
    job_id = enqueue(cx, "correct_muster_tail", {"drill": drill_code, "correction_id": ticket_id})
    row = cx.execute(
        """UPDATE muster_corrections SET status='queued',detail=NULL,job_id=%s,updated_at=now()
           WHERE id=%s RETURNING *""",
        (job_id, ticket_id),
    ).fetchone()
    return {"ticket": row, "job_id": job_id}
