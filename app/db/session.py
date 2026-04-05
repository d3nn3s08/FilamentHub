from contextlib import contextmanager
from typing import Iterator, Any

from sqlmodel import Session

from app.database import engine


@contextmanager
def session_scope() -> Iterator[Any]:
    """Context manager to provide a SQLModel `Session` bound to the global engine.

    This returns ``Any`` so that route modules that use the session can
    call raw SQL via ``text()`` without type-checker overload complaints.

    Usage:
        with session_scope() as session:
            # use session
    """
    with Session(engine) as session:
        yield session
