from pathlib import Path

from sqlalchemy import update
from sqlmodel import Session, SQLModel, create_engine

from app.models import Attempt


class AttemptStore:
    def __init__(self, database: Path):
        database.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            "sqlite:///" + str(database),
            connect_args={"check_same_thread": False, "timeout": 10},
            hide_parameters=True,
        )
        SQLModel.metadata.create_all(self.engine)

    def save(self, attempt: Attempt) -> None:
        # Detached snapshots + merge ensure JSON mutations are saved on every step.
        with Session(self.engine) as session:
            session.merge(attempt)
            session.commit()

    def get(self, attempt_id: str) -> Attempt:
        with Session(self.engine) as session:
            attempt = session.get(Attempt, attempt_id)
            if attempt is None:
                raise KeyError("Attempt not found")
            session.expunge(attempt)
            return attempt

    def claim(self, attempt_id: str) -> Attempt | None:
        # A repeated job must never submit another payment for the same attempt.
        with Session(self.engine) as session:
            result = session.execute(
                update(Attempt)
                .where(
                    Attempt.id == attempt_id,
                    Attempt.status == "queued",
                )
                .values(status="extracting")
            )
            session.commit()
            if result.rowcount != 1:
                return None
        return self.get(attempt_id)
