"""Per-user usage statistics for the Statistics page."""

import statistics
from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from auth import get_current_user
from db import get_db
from documents import count_documents
from models.message import Message
from models.project import Project
from models.session import Session as ChatSession
from models.template import PromptTemplate
from models.user import User

router = APIRouter(tags=["Statistics"])

ACTIVITY_DAYS = 14
MAX_REASONABLE_RESPONSE_S = 600  # ignore gaps where the user came back much later


def _grounding(sources: list | None) -> str:
    kinds = {s.get("type") for s in sources or []}
    if {"document", "web"} <= kinds:
        return "both"
    if "document" in kinds:
        return "documents"
    if "web" in kinds:
        return "web"
    return "model"


@router.get("/stats")
def get_stats(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    messages = (db.query(Message).filter(Message.user_id == user.id)
                .order_by(Message.session_id, Message.created_at, Message.id).all())
    questions = [m for m in messages if m.role == "user"]
    answers = [m for m in messages if m.role == "ai"]

    # Questions per day, oldest first, including days with none.
    today = date.today()
    per_day = Counter(m.created_at.date() for m in questions if m.created_at)
    activity = [{"date": (today - timedelta(days=i)).isoformat(), "questions": per_day.get(today - timedelta(days=i), 0)}
                for i in range(ACTIVITY_DAYS - 1, -1, -1)]

    # Response time: each answer measured from the question right before it in the same chat.
    durations = []
    for previous, current in zip(messages, messages[1:]):
        if (previous.session_id == current.session_id and previous.role == "user" and current.role == "ai"
                and previous.created_at and current.created_at):
            seconds = (current.created_at - previous.created_at).total_seconds()
            if 0 <= seconds <= MAX_REASONABLE_RESPONSE_S:
                durations.append(seconds)

    grounding = Counter(_grounding(m.sources) for m in answers)
    cited = Counter()
    for m in answers:
        for title in {s.get("title") for s in m.sources or [] if s.get("type") == "document"}:
            cited[title] += 1

    try:
        documents = count_documents(user.id)
    except Exception:
        documents = None  # Qdrant unavailable; the page shows "—"

    return {
        "totals": {
            "chats": db.query(ChatSession).filter(ChatSession.user_id == user.id).count(),
            "questions": len(questions),
            "documents": documents,
            "projects": db.query(Project).filter(Project.user_id == user.id).count(),
            "templates": db.query(PromptTemplate).filter(PromptTemplate.user_id == user.id).count(),
        },
        "activity": activity,
        "response_time": {
            "samples": len(durations),
            "median_s": round(statistics.median(durations), 1) if durations else None,
            "p90_s": round(statistics.quantiles(durations, n=10)[-1], 1) if len(durations) >= 2 else None,
        },
        "grounding": {key: grounding.get(key, 0) for key in ("documents", "web", "both", "model")},
        "top_documents": [{"title": t, "answers": n} for t, n in cited.most_common(5)],
    }
