from sqlmodel import Session, select
from app.database import get_engine
from app.models.settings import Setting

engine = get_engine()
with Session(engine) as s:
    rows = s.exec(select(Setting).where(Setting.key.like('logging.%'))).all()
    for r in rows:
        print(r.key, '=>', r.value)
