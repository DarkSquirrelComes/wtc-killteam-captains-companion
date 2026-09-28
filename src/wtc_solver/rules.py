"""Pure transitions; no payoffs, equilibrium calculations, or private actions."""
from dataclasses import replace
from .models import Event, History, IllegalAction, Match, Position, Stage, State, Team

def check_team(team):
    if team not in ("A", "B"):
        raise IllegalAction("Team must be 'A' or 'B'")

class Rules:
    def __init__(self, attacker_team: Team = "A"):
        check_team(attacker_team)
        self.attacker = attacker_team
        self.defender = "B" if attacker_team == "A" else "A"

    def initial(self) -> State:
        return State(Position(Stage.DEFENDER_BAN, tuple(range(9))))

    def actors(self, p: Position) -> tuple[Team, ...]:
        s = p.stage
        if s in (Stage.SHIELDS, Stage.SWORDS):
            return ("A", "B")
        if s == Stage.TERMINAL:
            return ()
        return (self.attacker if s in (Stage.ATTACKER_BAN, Stage.DEFENDER_TABLE,
                                       Stage.ATTACKER_MISSION) else self.defender,)

    def legal_actions(self, p: Position, team: Team) -> tuple[int, ...]:
        check_team(team)
        if team not in self.actors(p):
            return ()
        if p.stage == Stage.SHIELDS:
            return (0,1,2)
        if p.stage == Stage.SWORDS:
            opposing_shield = p.shields[1 if team == "A" else 0]
            return tuple(i for i in range(3) if i != opposing_shield)
        return p.tables if p.stage in (Stage.DEFENDER_TABLE, Stage.ATTACKER_TABLE) else p.missions

    def transition(self, p: Position, actions: tuple[int, ...]) -> tuple[Position, Match | None]:
        """Return (future position, newly completed match or None)."""
        actors = self.actors(p)
        if not isinstance(actions, tuple) or not actors or len(actions) != len(actors):
            raise IllegalAction("Supply exactly one action per current actor; reveal simultaneous actions together")
        for team, action in zip(actors, actions):
            if type(action) is not int or action not in self.legal_actions(p, team):
                raise IllegalAction(f"Illegal {team} action {action!r} at {p.stage.name}")
        s = p.stage
        if s in (Stage.DEFENDER_BAN, Stage.ATTACKER_BAN):
            return replace(p, stage=Stage(s+1), missions=tuple(m for m in p.missions if m != actions[0])), None
        if s == Stage.SHIELDS:
            return replace(p, stage=Stage.SWORDS, shields=tuple(actions)), None
        if s == Stage.SWORDS:
            sa,sb = p.shields
            chosen_b,chosen_a = actions
            shield_a = (sa,chosen_b)
            shield_b = (chosen_a,sb)
            rest = (3-sa-chosen_a, 3-sb-chosen_b)
            pairs = (shield_b,shield_a,rest) if self.attacker == "A" else (shield_a,shield_b,rest)
            return replace(p, stage=Stage.DEFENDER_TABLE, shields=(), pairs=pairs), None
        if s in (Stage.DEFENDER_TABLE, Stage.ATTACKER_TABLE):
            return replace(p, stage=Stage(s+1), table=actions[0]), None
        mission = actions[0]
        table = p.tables[0] if s == Stage.LAST_MISSION else p.table
        match = Match(*p.pairs[0],table,mission)
        if s == Stage.LAST_MISSION:
            return Position(Stage.TERMINAL, tuple(m for m in p.missions if m != mission), ()), match
        return Position(Stage(s+1), tuple(m for m in p.missions if m != mission),
                        tuple(t for t in p.tables if t != table), pairs=p.pairs[1:]), match

    def apply(self, state: State, event: Event) -> State:
        if not isinstance(event, Event):
            raise IllegalAction("History entries must be Event records")
        p,match = self.transition(state.position,event.actions)
        return State(p, state.matches + ((match,) if match else ()))

    def replay(self, history: History = ()) -> State:
        state = self.initial()
        for event in history:
            state = self.apply(state,event)
        return state
