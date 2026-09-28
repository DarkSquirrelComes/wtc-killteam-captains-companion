"""Typed presentation records and exact percentage rounding; no game rules."""
from dataclasses import dataclass
from fractions import Fraction
from wtc_solver.models import GameValue, Stage

STAGE_TITLES = {
    Stage.DEFENDER_BAN: 'Бан миссии защитником',
    Stage.ATTACKER_BAN: 'Бан миссии атакующим',
    Stage.SHIELDS: 'Одновременный выбор щитов',
    Stage.SWORDS: 'Одновременный выбор мечей',
    Stage.DEFENDER_TABLE: 'Стол для щита защитника',
    Stage.DEFENDER_MISSION: 'Миссия для щита защитника',
    Stage.ATTACKER_TABLE: 'Стол для щита атакующего',
    Stage.ATTACKER_MISSION: 'Миссия для щита атакующего',
    Stage.LAST_MISSION: 'Миссия для оставшихся мечей',
    Stage.TERMINAL: 'Паринг завершён',
}

@dataclass(frozen=True, slots=True)
class ActionOption:
    id: int
    name: str
    probability: Fraction | None
    percent: str | None
    expected_a: Fraction | None
    guarantee_a: Fraction | None

@dataclass(frozen=True, slots=True)
class PairView:
    ours: str
    opponent: str
    table: str | None
    mission: str | None
    gp_a: Fraction | None
    gp_b: Fraction | None

@dataclass(frozen=True, slots=True)
class ResourceView:
    name: str
    status: str

@dataclass(frozen=True, slots=True)
class DecisionView:
    context: str
    stage: Stage
    title: str
    mode: str  # own / opponent / reveal / complete
    our_role: str
    options: tuple[ActionOption, ...]
    value: GameValue
    simultaneous: bool
    own_commitment: str | None
    pairs: tuple[PairView, ...]
    missions: tuple[ResourceView, ...]
    tables: tuple[ResourceView, ...]
    shields: tuple[str, str] | None
    history: tuple[str, ...]
    explanation: str

def percentages(probabilities: tuple[Fraction, ...]) -> tuple[str, ...]:
    """Largest remainder, stable index ties, one decimal; sum exactly 100.0%."""
    if not probabilities: return ()
    if sum(probabilities) != 1 or any(p < 0 for p in probabilities):
        raise ValueError('Invalid distribution')
    scaled = [p*1000 for p in probabilities]
    units = [int(x) for x in scaled]
    order = sorted(range(len(units)), key=lambda i: (-(scaled[i]-units[i]), i))
    for i in order[:1000-sum(units)]: units[i] += 1
    return tuple(f'{u//10}.{u%10}%' for u in units)
