"""Ask Me API — chat with JeromeLu."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from jeromelu_shared.rag import ask_jeromelu

from ..deps import get_db

router = APIRouter()


class AskRequest(BaseModel):
    question: str = Field(..., max_length=500)
    temperature: str = Field(default="sharp", pattern="^(straight|sharp|roast)$")


class SourceRef(BaseModel):
    source_id: str
    title: str
    creator_name: str | None = None


class PlayerRef(BaseModel):
    entity_id: str
    name: str


class AskResponse(BaseModel):
    answer: str
    sources: list[SourceRef]
    players: list[PlayerRef]
    kb_entries_used: list[str]


@router.post("/ask", response_model=AskResponse)
def ask(body: AskRequest, db: Session = Depends(get_db)):
    """Ask JeromeLu a question about NRL SuperCoach."""
    result = ask_jeromelu(db, body.question, body.temperature)
    return AskResponse(**result)
