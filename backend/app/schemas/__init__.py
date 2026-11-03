from pydantic import BaseModel


class TestSchema(BaseModel):
    name: str
    value: int
