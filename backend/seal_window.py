from fastapi import HTTPException
from core import enqueue
from drill_registry import drill

def seal(cx,code):
    row=drill(cx,code,True)
    if row["status"]!="open":
        raise HTTPException(409,"该观察窗已冻结")
    pending=cx.execute("""SELECT count(*) AS missing FROM muster_members m LEFT JOIN muster_clock o
      ON o.drill=m.drill AND o.code=m.code WHERE m.drill=%s AND o.code IS NULL""",(code,)).fetchone()["missing"]
    if pending:
        raise HTTPException(409,f"{pending} 位的观察单未登记，请确认签到或右删失")
    cx.execute("UPDATE muster_drills SET status='sealed' WHERE code=%s",(code,))
    return {"job_id":enqueue(cx,"estimate_muster_tail",{"drill":code})}
