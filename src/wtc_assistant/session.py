"""Persistent immutable session state: public history plus OUR private choice."""
from dataclasses import dataclass
from uuid import uuid4
from wtc_solver.models import History, Team

@dataclass(frozen=True, slots=True)
class CaptainSession:
    attacker_team: Team
    history: History = ()
    own_commitment: int | None = None
    revision: int = 0
    session_id: str = ''

    @classmethod
    def new(cls, attacker_team: Team):
        return cls(attacker_team, session_id=uuid4().hex)

@dataclass(frozen=True, slots=True)
class Proposal:
    action: int
    context: str
    sampled: bool
