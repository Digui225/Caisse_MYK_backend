"""Compteurs verrouillés (`sequence_counters`) : n° de Z par caisse, n° de commande par journée…"""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from caisse.models.settings import SequenceCounter


def next_value(db: Session, key: str) -> int:
    """Incrémente et retourne le compteur `key`, en le créant s'il n'existe pas.

    `INSERT ... ON CONFLICT DO NOTHING` neutralise la course à la création, puis
    `SELECT ... FOR UPDATE` sérialise les transactions concurrentes sur la même clé.
    """
    db.execute(insert(SequenceCounter).values(key=key, value=0).on_conflict_do_nothing())
    counter = db.execute(
        select(SequenceCounter).where(SequenceCounter.key == key).with_for_update()
    ).scalar_one()
    counter.value += 1
    db.flush()
    return counter.value
