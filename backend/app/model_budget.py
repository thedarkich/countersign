"""Durable, atomic rolling-hour reservations; a call count is not a dollar budget."""

import time
from uuid import uuid4

from sqlalchemy import delete, func, insert, select, text

from app.models import ModelCallReservation


class BudgetExhausted(Exception):
    pass


class ModelCallBudget:
    def __init__(self, engine, cap, *, clock=time.time):
        self.engine, self.cap, self.clock = engine, cap, clock

    def _count(self, conn, now):
        return conn.execute(
            select(func.count())
            .select_from(ModelCallReservation)
            .where(ModelCallReservation.reserved_at > now - 3600)
        ).scalar_one()

    def exhausted(self):
        with self.engine.connect() as conn:
            return self._count(conn, self.clock()) >= self.cap

    def reserve(self):
        # Commit before making a provider request. Failed/abandoned requests count;
        # never refund an uncertain result or reset the budget on service restart.
        with self.engine.connect() as conn:
            conn.execute(text("BEGIN IMMEDIATE"))
            try:
                now = self.clock()
                if self._count(conn, now) >= self.cap:
                    raise BudgetExhausted
                conn.execute(
                    delete(ModelCallReservation).where(
                        ModelCallReservation.reserved_at <= now - 3600
                    )
                )
                conn.execute(insert(ModelCallReservation).values(id=str(uuid4()), reserved_at=now))
                conn.commit()
            except Exception:
                conn.rollback()
                raise
