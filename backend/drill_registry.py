from fastapi import HTTPException

def drill(cx, code, lock=False):
    suffix = " FOR UPDATE" if lock else ""
    row = cx.execute("SELECT * FROM muster_drills WHERE code=%s"+suffix,(code,)).fetchone()
    if row is None:
        raise HTTPException(404,"演练窗口未登记")
    return row

def roster(cx, code):
    drill(cx,code)
    return cx.execute("""SELECT m.*,o.seconds,o.kind FROM muster_members m LEFT JOIN muster_clock o
      ON o.drill=m.drill AND o.code=m.code WHERE m.drill=%s ORDER BY m.group_name,m.code""",(code,)).fetchall()
