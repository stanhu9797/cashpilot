from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..ai.client import AIUnavailable
from ..auth import current_user
from ..database import get_db
from ..models import User
from ..schemas import AskIn
from ..services.ask import answer_question
from .. import ratelimit

router = APIRouter(prefix="/api/ask", tags=["ask"])


@router.post("")
def ask(body: AskIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    ratelimit.check(f"ask:{user.id}", 30, 3600, "Too many questions in the last hour.")
    try:
        return answer_question(db, user.id, body.question.strip())
    except AIUnavailable as e:
        raise HTTPException(503, str(e))
