from datetime import date
from pydantic import BaseModel, Field

class Member(BaseModel):
    code:str=Field(pattern=r"^[A-Z0-9-]{2,16}$")
    group_name:str=Field(min_length=2,max_length=32)

class DrillInput(BaseModel):
    code:str=Field(pattern=r"^[A-Z0-9-]{3,16}$")
    title:str=Field(min_length=4,max_length=80)
    day:date
    cutoff:int=Field(ge=10,le=1800)
    members:list[Member]=Field(min_length=2,max_length=200)
