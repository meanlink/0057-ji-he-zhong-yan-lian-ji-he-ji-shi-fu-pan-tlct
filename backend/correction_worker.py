"""曲线更正重算：在单个事务内完成检测、退回或原子切换。"""
from fastapi import HTTPException

from correction_log import blocking_followups
from drill_registry import drill, roster
from survival import estimate
from tail_persist import read as read_tail


def run(cx, kind, data):
    if kind != "correct_muster_tail":
        raise ValueError(kind)
    drill_code = data["drill"]
    ticket_id = data["correction_id"]
    # 与开补查、封存、重试互斥：整个重算期间锁住演练行。
    window = drill(cx, drill_code, True)
    ticket = cx.execute(
        "SELECT * FROM muster_corrections WHERE id=%s AND drill=%s FOR UPDATE",
        (ticket_id, drill_code),
    ).fetchone()
    if ticket is None:
        raise HTTPException(404, "没有这张更正单")
    # 幂等防御：已生效的更正单即使被重复投递也不再发布。
    if ticket["status"] == "effective":
        return {"outcome": "already_effective", "correction_id": ticket_id,
                "tail": read_tail(cx, drill_code)}
    if window["status"] != "calculated":
        raise HTTPException(409, "演练窗口状态已变化，无法应用更正")

    cx.execute("UPDATE muster_corrections SET status='running',updated_at=now() WHERE id=%s",
               (ticket_id,))
    observations = ticket["observations"]

    blocked = blocking_followups(cx, drill_code, observations)
    if blocked:
        # 补查单先开成：更正退回复核，原曲线与原件保持有效（本事务只改更正单状态）。
        detail = "以下记录已先开立补查单，请先核对凭据后重新发起：" + "、".join(blocked)
        cx.execute(
            "UPDATE muster_corrections SET status='returned',detail=%s,updated_at=now() WHERE id=%s",
            (detail, ticket_id),
        )
        return {"outcome": "returned", "correction_id": ticket_id, "detail": detail,
                "tail": read_tail(cx, drill_code)}

    _apply(cx, drill_code, observations)
    cx.execute(
        "UPDATE muster_corrections SET status='effective',detail=NULL,updated_at=now() WHERE id=%s",
        (ticket_id,),
    )
    return {"outcome": "effective", "correction_id": ticket_id,
            "tail": read_tail(cx, drill_code)}


def _apply(cx, drill_code, observations):
    """原子切换：曲线与补查资格引用的签到原件在同一事务内整体替换。"""
    # 再校验一次名册与窗口规则，防止在途期间名册被改动。
    window = drill(cx, drill_code)
    members = {row["code"] for row in roster(cx, drill_code)}
    if {item["code"] for item in observations} != members:
        raise HTTPException(409, "名册已变化，请重新发起更正")
    cutoff = window["cutoff"]
    for item in observations:
        if item["seconds"] > cutoff:
            raise HTTPException(409, f"{item['code']} 的时间超过观察窗")
        if item["kind"] == "censored" and item["seconds"] != cutoff:
            raise HTTPException(409, f"{item['code']} 的右删失时刻必须等于观察窗截止时刻")

    cx.execute("DELETE FROM muster_curves WHERE drill=%s", (drill_code,))
    # 原地更新签到原件：muster_followup 对 muster_clock 有外键，
    # 全量覆盖且成员集合不变时用 UPSERT 保留引用关系，避免删除违约。
    for item in observations:
        cx.execute(
            """INSERT INTO muster_clock VALUES (%s,%s,%s,%s)
               ON CONFLICT(drill,code) DO UPDATE
               SET seconds=excluded.seconds, kind=excluded.kind""",
            (drill_code, item["code"], item["seconds"], item["kind"]),
        )
    for row in estimate(observations):
        cx.execute(
            """INSERT INTO muster_curves
               VALUES (%(drill)s,%(seconds)s,%(at_risk)s,%(arrivals)s,%(censored)s,%(remaining)s)""",
            row | {"drill": drill_code},
        )
    # 演练状态保持 calculated：曲线已发布，只是版本被更正。
    cx.execute("UPDATE muster_drills SET status='calculated' WHERE code=%s", (drill_code,))
