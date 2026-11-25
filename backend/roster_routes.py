from fastapi import APIRouter, Depends
from core import db, require
from drill_registry import roster
from drill_input import DrillInput

router=APIRouter(prefix="/muster-drills")

@router.get("")
def listing(_=Depends(require())):
    with db() as cx:
        return cx.execute("SELECT * FROM muster_drills ORDER BY day DESC,code").fetchall()

@router.get("/{code}/roster")
def roster_view(code:str,_=Depends(require())):
    with db() as cx:
        return roster(cx,code)

@router.post("",status_code=201)
def enroll(body:DrillInput,_=Depends(require("operator"))):
    with db() as cx:
        row=cx.execute("INSERT INTO muster_drills(code,title,day,cutoff) VALUES (%s,%s,%s,%s) RETURNING *",
                       (body.code,body.title,body.day,body.cutoff)).fetchone()
        for member in body.members:
            cx.execute("INSERT INTO muster_members VALUES (%s,%s,%s)",(body.code,member.code,member.group_name))
        return row
