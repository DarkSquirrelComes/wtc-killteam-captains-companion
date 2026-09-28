"""Immutable public records. IDs are zero-based within each entity category."""
from dataclasses import dataclass
from enum import IntEnum
from fractions import Fraction
from typing import Literal

Team = Literal['A', 'B']
History = tuple['Event', ...]

class Stage(IntEnum):
    DEFENDER_BAN = 0
    ATTACKER_BAN = 1
    SHIELDS = 2
    SWORDS = 3
    DEFENDER_TABLE = 4
    DEFENDER_MISSION = 5
    ATTACKER_TABLE = 6
    ATTACKER_MISSION = 7
    LAST_MISSION = 8
    TERMINAL = 9

class IllegalAction(ValueError):
    """An action, actor, or history violates the pairing rules."""

class InvalidData(ValueError):
    """Malformed, incompatible, or corrupted input."""

@dataclass(frozen=True, slots=True)
class Position:
    """Future-only state; excludes completed matches and their accrued GP."""
    stage: Stage
    missions: tuple[int, ...]
    tables: tuple[int, ...] = (0, 1, 2)
    shields: tuple[int, ...] = ()  # A, B
    pairs: tuple[tuple[int, int], ...] = ()  # remaining, in play order
    table: int = -1

@dataclass(frozen=True, slots=True)
class Match:
    a: int
    b: int
    table: int
    mission: int

@dataclass(frozen=True, slots=True)
class Event:
    """One public decision. Simultaneous actions always occur in A,B order."""
    actions: tuple[int, ...]

@dataclass(frozen=True, slots=True)
class State:
    position: Position
    matches: tuple[Match, ...] = ()

@dataclass(frozen=True, slots=True)
class GameValue:
    """Expected FINAL GP, conditional on public history and optimal future play."""
    team_a: Fraction
    team_b: Fraction
    accrued_a: Fraction
    remaining_a: Fraction

@dataclass(frozen=True, slots=True)
class Recommendation:
    team: Team
    stage: Stage
    actions: tuple[int, ...]
    probabilities: tuple[Fraction, ...]
    value: GameValue
    simultaneous: bool
    action_kind: str

@dataclass(frozen=True, slots=True)
class Node:
    """Expected remaining A GP and strategies; empty strategies for non-actors."""
    value: Fraction
    a: tuple[Fraction, ...]
    b: tuple[Fraction, ...]

@dataclass(frozen=True, slots=True)
class ActionValue:
    """FINAL expected A GP after one action, with optimal subsequent play.

    At simultaneous stages, expectation is against the stored opposing mixture,
    NOT a guarantee for this pure action. guarantee_for_team is the worst case
    over opposing current actions, followed by our optimal continuation; it
    concerns supplied expected GP, never the score of a real played match.
    """
    action: int
    expected_a: Fraction
    guarantee_for_team: Fraction
    against_equilibrium_mix: bool
