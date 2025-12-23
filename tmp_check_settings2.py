from sqlmodel import Session, select
from app.database import engine
from app.models.settings import Setting

with Session(engine) as s:
    rows = s.exec(select(Setting).where(Setting.key.like('logging.%'))).all()
    for r in rows:
        print(r.key, '=>', r.value)
