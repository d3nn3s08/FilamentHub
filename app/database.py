from sqlmodel import SQLModel, Session, create_engine
import os

DB_PATH = os.environ.get("FILAMENTHUB_DB_PATH", "data/filamenthub.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db() -> None:
    """
    Erstellt alle Tabellen, falls sie noch nicht existieren.
    Wichtig: Modelle müssen vor dem Aufruf importiert sein.
    """
    from app.models.material import Material  # noqa: F401
    from app.models.spool import Spool  # noqa: F401
    from app.models.printer import Printer  # noqa: F401
    from app.models.job import Job  # noqa: F401

    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Dependency für FastAPI-Routen.
    """
    with Session(engine) as session:
        yield session
