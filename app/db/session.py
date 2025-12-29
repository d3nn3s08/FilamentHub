from contextlib import contextmanager
from typing import Iterator

from sqlmodel import Session

from app.database import engine


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager to provide a SQLModel `Session` bound to the global engine.

    Usage:
        with session_scope() as session:
            # use session
    """
    with Session(engine) as session:
        yield session
