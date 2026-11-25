from fastapi import APIRouter,Depends
from core import db,require
from followup_input import Followup
from followup_log import collect_followup

router=APIRouter(prefix="/muster-drills/{code}/followup")

@router.get("")
def history(code:str,_=Depends(require())):
    with db() as cx:
        return cx.execute("SELECT * FROM muster_followup WHERE drill=%s ORDER BY code",(code,)).fetchall()

@router.post("",status_code=201)
def register(code:str,body:Followup,user=Depends(require("reviewer"))):
    with db() as cx:
        return collect_followup(cx,code,body,user["email"])
