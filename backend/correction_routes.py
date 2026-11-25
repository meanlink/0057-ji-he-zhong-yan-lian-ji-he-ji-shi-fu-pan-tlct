from fastapi import APIRouter, Depends

from correction_input import Correction
from correction_log import list_corrections, open_correction, retry_correction
from core import db, require

router = APIRouter(prefix="/muster-drills/{code}/corrections")


@router.get("")
def history(code: str, _=Depends(require())):
    with db() as cx:
        return list_corrections(cx, code)


@router.post("", status_code=201)
def open_ticket(code: str, body: Correction, user=Depends(require("reviewer"))):
    with db() as cx:
        return open_correction(cx, code, body, user["email"])


@router.post("/{ticket_id}/retry", status_code=202)
def retry_ticket(code: str, ticket_id: int, _=Depends(require("reviewer"))):
    with db() as cx:
        return retry_correction(cx, code, ticket_id)
