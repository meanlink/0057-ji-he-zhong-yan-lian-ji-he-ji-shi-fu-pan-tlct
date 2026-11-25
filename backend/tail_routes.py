from fastapi import APIRouter,Depends
from core import db,require
from seal_window import seal
from tail_persist import read

router=APIRouter(prefix="/muster-drills/{code}/tail")

@router.get("")
def digest(code:str,_=Depends(require())):
    with db() as cx:
        return read(cx,code)

@router.post("",status_code=202)
def queue(code:str,_=Depends(require("reviewer"))):
    with db() as cx:
        return seal(cx,code)
