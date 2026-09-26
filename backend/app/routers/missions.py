import uuid
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import MissionInstance, User
from app.schemas.mission import MissionInstanceRead
from app.services.planner import ensure_missions, missions_on

router = APIRouter(prefix="/missions", tags=["missions"])


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "date must be 'today' or YYYY-MM-DD"
        ) from None


@router.get("", response_model=list[MissionInstanceRead])
def list_missions(
    date_param: Annotated[str, Query(alias="date", max_length=10)] = "today",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MissionInstance]:
    """The player's missions for a date. Today's missions are planned on first request.

    "Today" is the player's local date (their `time_zone`). Outside programme days 1-90 nothing is
    planned and the list is empty.
    """
    # Resolve the player's local "today" once, so a request spanning midnight can't disagree
    # with itself.
    today = datetime.now(ZoneInfo(user.time_zone)).date()
    day = today if date_param == "today" else _parse_date(date_param)
    if day == today:
        # Outside days 1-90 ensure_missions plans nothing and returns [], so this is 200 + [].
        return ensure_missions(db, user, day)
    return missions_on(db, user, day)


@router.get("/{mission_id}", response_model=MissionInstanceRead)
def get_mission(
    mission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MissionInstance:
    mission = db.get(MissionInstance, mission_id)
    # 404 (not 403) for other users' missions so ids can't be probed.
    if mission is None or mission.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mission not found")
    return mission
