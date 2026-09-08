from pydantic import BaseModel


class CounselTurnRequest(BaseModel):
    user_text: str


class CounselTurnResponse(BaseModel):
    reply: str