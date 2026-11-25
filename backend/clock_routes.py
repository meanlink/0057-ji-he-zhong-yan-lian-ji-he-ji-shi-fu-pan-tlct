from fastapi import APIRouter, Depends
from core import db, require
from clock_input import Observation
from clock_log import enter

router=APIRouter(prefix="/muster-drills/{code}")

@router.put("/clock")
def enter_time(code:str,body:Observation,_=Depends(require("operator"))):
    with db() as cx:
        return enter(cx,code,body)
