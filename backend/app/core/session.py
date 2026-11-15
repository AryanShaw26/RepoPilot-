import uuid
from typing import Optional
from fastapi import Depends, Header, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import SessionModel
from app.db.session import get_db


async def get_or_create_session_id(
    response: Response,
    x_session_id: Optional[str] = Header(None, alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
) -> uuid.UUID:
    session_uuid: Optional[uuid.UUID] = None

    if x_session_id:
        try:
            session_uuid = uuid.UUID(x_session_id)
        except ValueError:
            session_uuid = None

    if session_uuid:
        # Check if session exists in DB
        res = await db.execute(select(SessionModel).where(SessionModel.id == session_uuid))
        existing = res.scalar_one_or_none()
        if existing:
            response.headers["X-Session-Id"] = str(session_uuid)
            return session_uuid

    # Create new session
    new_session = SessionModel()
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)

    response.headers["X-Session-Id"] = str(new_session.id)
    return new_session.id
