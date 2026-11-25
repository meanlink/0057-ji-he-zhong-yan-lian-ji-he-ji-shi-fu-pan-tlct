from fastapi import HTTPException
from drill_registry import drill

def enter(cx,code,data):
    window=drill(cx,code,True)
    if window["status"]!="open":
        raise HTTPException(409,"观察窗已封存")
    if data.seconds>window["cutoff"]:
        raise HTTPException(409,"签到时间超过观察窗，请核对是否作为右删失")
    if data.kind=="censored" and data.seconds!=window["cutoff"]:
        raise HTTPException(409,"右删失记录只能使用观察窗截止时刻")
    known=cx.execute("SELECT 1 FROM muster_members WHERE drill=%s AND code=%s",(code,data.code)).fetchone()
    if not known:
        raise HTTPException(409,"观察码不在本轮名册")
    return cx.execute("""
      INSERT INTO muster_clock VALUES (%s,%s,%s,%s)
      ON CONFLICT(drill,code) DO UPDATE SET seconds=excluded.seconds,kind=excluded.kind
      RETURNING *
    """,(code,data.code,data.seconds,data.kind)).fetchone()
