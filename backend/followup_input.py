from pydantic import BaseModel,Field

class Followup(BaseModel):
    code:str=Field(pattern=r"^[A-Z0-9-]{2,16}$")
    action:str=Field(min_length=5,max_length=200)
