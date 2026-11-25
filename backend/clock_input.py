from typing import Literal
from pydantic import BaseModel,Field

class Observation(BaseModel):
    code:str=Field(pattern=r"^[A-Z0-9-]{2,16}$")
    seconds:int=Field(ge=1,le=1800)
    kind:Literal['arrived','censored']
