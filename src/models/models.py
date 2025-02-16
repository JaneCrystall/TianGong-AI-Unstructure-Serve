from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class TextElementWithPageNum(BaseModel):
    text: str
    page_number: int


class ResponseWithPageNum(BaseModel):
    result: List[TextElementWithPageNum]

    @classmethod
    def from_result(cls, result: List[Tuple[str, int]]):
        items = [TextElementWithPageNum(text=item[0], page_number=item[1]) for item in result]
        return cls(result=items)


class TextElementWithoutPageNum(BaseModel):
    text: str


class ResponseWithoutPageNum(BaseModel):
    result: List[TextElementWithoutPageNum]

    @classmethod
    def from_result(cls, result: List[Tuple[str, int]]):
        items = [TextElementWithoutPageNum(text=item) for item in result]
        return cls(result=items)
