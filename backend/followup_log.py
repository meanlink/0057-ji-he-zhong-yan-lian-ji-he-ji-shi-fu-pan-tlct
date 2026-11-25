from fastapi import HTTPException
from drill_registry import drill

def collect_followup(cx, key, data, owner):
    window=drill(cx,key,True)
    if window["status"]!="calculated":
        raise HTTPException(409,"先生成该场观察窗的时效统计")
    evidence=cx.execute("SELECT kind FROM muster_clock WHERE drill=%s AND code=%s",(key,data.code)).fetchone()
    if evidence is None or evidence["kind"]!="censored":
        raise HTTPException(409,"漏记补查须绑定一条到截止仍未签到的观察记录")
    return cx.execute("INSERT INTO muster_followup VALUES (%s,%s,%s,%s) RETURNING *",(key,data.code,owner,data.action)).fetchone()
