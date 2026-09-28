"""Calculate each role explicitly, retain immutable policies and reusable exports."""
from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Callable
from wtc_solver import InvalidData, Solution, solve
from wtc_solver.serialization import dumps
from .config import Configuration, Names

@dataclass(frozen=True, slots=True)
class PolicyBundle:
    config: Configuration
    attacker_a: Solution
    attacker_b: Solution
    documents: tuple[str, str]

    @classmethod
    def create(cls, config: Configuration, a: Solution, b: Solution):
        if a.attacker_team != 'A' or b.attacker_team != 'B':
            raise InvalidData('Нужны решения для двух разных ролей нашей команды.')
        if any(s.payoffs != config.payoffs for s in (a,b)):
            raise InvalidData('Политика не соответствует таблице GP.')
        return cls(config, a, b, (dumps(a), dumps(b)))

    def solution(self, attacker_team: str) -> Solution:
        if attacker_team not in ('A', 'B'):
            raise InvalidData('Неверное назначение ролей.')
        return self.attacker_a if attacker_team == 'A' else self.attacker_b

    @property
    def pre_roll_a(self) -> Fraction:
        return (self.attacker_a.get_value().team_a + self.attacker_b.get_value().team_a)/2

    def renamed(self, names: Names) -> 'PolicyBundle':
        """Explicit relabeling of existing IDs; does not change identities/GP/policies."""
        return replace(self, config=Configuration(self.config.payoffs, names))

def calculate(config: Configuration, progress: Callable[[str, int], None] | None = None) -> PolicyBundle:
    if progress: progress('Расчёт: наша команда — атакующий', 0)
    a = solve(config.payoffs, 'A')
    if progress: progress('Расчёт: наша команда — защитник', 1)
    b = solve(config.payoffs, 'B')
    bundle = PolicyBundle.create(config, a, b)
    if progress: progress('Обе роли рассчитаны', 2)
    return bundle
