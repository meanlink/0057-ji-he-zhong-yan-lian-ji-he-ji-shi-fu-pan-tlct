from typing import Literal
from pydantic import BaseModel, Field


class CorrectionObservation(BaseModel):
    code: str = Field(pattern=r"^[A-Z0-9-]{2,16}$")
    seconds: int = Field(ge=1, le=1800)
    kind: Literal["arrived", "censored"]


class Correction(BaseModel):
    reason: str = Field(min_length=5, max_length=200)
    observations: list[CorrectionObservation] = Field(min_length=1, max_length=200)
