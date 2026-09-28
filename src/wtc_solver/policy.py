"""Read-only policy access and a private-commit session controller.

History is PUBLIC revealed Event records only. A session's pending actions
are returned only in the corresponding captain's private export.
Use the caller's authentication layer to bind the team argument to a captain.
"""
from dataclasses import dataclass
from fractions import Fraction as F
from math import lcm
from typing import Mapping, Protocol
from .models import ActionValue, Event, GameValue, History, IllegalAction, Node, Position, Recommendation, Stage, State, Team
from .payoff import Payoffs
from .rules import Rules, check_team

@dataclass(frozen=True, slots=True)
class Solution:
    payoffs: Payoffs
    attacker_team: Team
    nodes: Mapping[Position, Node]
    statistics: Mapping[str, int | float]

    @property
    def rules(self) -> Rules:
        return Rules(self.attacker_team)

    def get_state(self, history: History = ()) -> State:
        return self.rules.replay(history)

    def get_value(self, history: History = ()) -> GameValue:
        state = self.get_state(history)
        accrued = sum((self.payoffs.gp(m) for m in state.matches),F(0))
        remaining = F(0) if state.position.stage == Stage.TERMINAL else self.nodes[state.position].value
        return GameValue(accrued+remaining,60-accrued-remaining,accrued,remaining)

    def get_recommendation(self, history: History, team: Team) -> Recommendation:
        check_team(team)
        history = tuple(history)
        p = self.get_state(history).position
        acts = self.rules.legal_actions(p,team)
        probs = () if not acts else (self.nodes[p].a if team=='A' else self.nodes[p].b)
        kind = ('player' if p.stage in (Stage.SHIELDS,Stage.SWORDS) else
                'table' if p.stage in (Stage.DEFENDER_TABLE,Stage.ATTACKER_TABLE) else
                'none' if p.stage == Stage.TERMINAL else 'mission')
        return Recommendation(team,p.stage,acts,probs,self.get_value(history),
                              p.stage in (Stage.SHIELDS,Stage.SWORDS),kind)

    def get_action_values(self, history: History, team: Team) -> tuple[ActionValue, ...]:
        """Evaluate alternatives from stored continuations, without solving again."""
        history = tuple(history)
        rec = self.get_recommendation(history, team)
        other = 'B' if team == 'A' else 'A'
        opponent = self.get_recommendation(history, other) if rec.simultaneous else None
        result = []
        for action in rec.actions:
            if opponent is None:
                value = self.get_value(history + (Event((action,)),)).team_a
                guarantee = value if team == 'A' else 60-value
            else:
                values = []
                for opposing in opponent.actions:
                    choices = (action, opposing) if team == 'A' else (opposing, action)
                    values.append(self.get_value(history + (Event(choices),)).team_a)
                value = sum((p*v for p,v in zip(opponent.probabilities, values)), F(0))
                guarantee = min(values) if team == 'A' else 60-max(values)
            result.append(ActionValue(action, value, guarantee, rec.simultaneous))
        return tuple(result)

class RandomSource(Protocol):
    def randrange(self, stop: int) -> int: ...

def sample_action(recommendation: Recommendation, rng: RandomSource) -> int:
    """Sample exact rational weights using an injected RNG with randrange(n)."""
    ps = recommendation.probabilities
    if not ps or sum(ps)!=1 or any(p<0 for p in ps):
        raise IllegalAction("No valid action distribution to sample")
    denominator = lcm(*(p.denominator for p in ps))
    draw = rng.randrange(denominator)
    for action,p in zip(recommendation.actions,ps):
        draw -= p.numerator*(denominator//p.denominator)
        if draw < 0:
            return action
    raise ArithmeticError("Invalid RNG result")

class Session:
    """Controller for revealed history and private pending simultaneous choices.

    Public views reveal no pending actions (including to their owner). Recommit
    overwrites one's own choice until both are submitted. The second submission
    atomically reveals an Event. Undo clears pending choices first; otherwise it
    removes one whole public event. No opponent commitment-status endpoint exists.
    """
    def __init__(self, solution: Solution, history: History = ()):
        self.solution = solution
        self.__history = list(history)
        solution.get_state(self.__history)
        self.__pending = {}

    @property
    def history(self) -> History:
        return tuple(self.__history)

    @property
    def state(self) -> State:
        return self.solution.get_state(self.__history)

    def recommendation(self, team: Team) -> Recommendation:
        return self.solution.get_recommendation(self.__history,team)

    def act(self, team: Team, action: int) -> Event | None:
        rules = self.solution.rules
        p = self.state.position
        if type(action) is not int or action not in rules.legal_actions(p,team):
            raise IllegalAction(f"Illegal action for team {team}")
        actors = rules.actors(p)
        if len(actors)==2:
            self.__pending[team] = action
            if len(self.__pending)<2:
                return None
            event = Event((self.__pending['A'],self.__pending['B']))
        else:
            event = Event((action,))
        rules.apply(self.state,event)
        self.__history.append(event)
        self.__pending.clear()
        return event

    def undo(self) -> None:
        if self.__pending:
            self.__pending.clear()
        elif self.__history:
            self.__history.pop()
        else:
            raise IllegalAction("No previous action")

    def export(self) -> str:
        """Public-session JSON, omitting private pending choices.

        To preserve an unfinished simultaneous stage, each captain separately
        saves export_private(team). Restore these together with this snapshot.
        Never send one captain's private export to the other captain.
        """
        from .serialization import pack
        return pack('session',dict(tensor=self.solution.payoffs.fingerprint,
                    attacker=self.solution.attacker_team,history=[list(e.actions) for e in self.history]))

    def export_private(self, team: Team) -> str:
        """Captain-scoped snapshot. The frontend must authorize the team argument."""
        from .serialization import pack
        import hashlib
        check_team(team)
        return pack('private-session',dict(public_sha256=hashlib.sha256(self.export().encode()).hexdigest(),
                    team=team,action=self.__pending.get(team)))

    @classmethod
    def restore(cls, solution: Solution, text: str, private_snapshots: tuple[str, ...] = ()) -> 'Session':
        from .serialization import unpack
        from .models import InvalidData
        data = unpack(text,'session')
        try:
            if data['tensor'] != solution.payoffs.fingerprint or data['attacker'] != solution.attacker_team:
                raise InvalidData("Session belongs to another tensor or role assignment")
            session = cls(solution,tuple(Event(tuple(a)) for a in data['history']))
            import hashlib
            digest = hashlib.sha256(text.encode()).hexdigest()
            seen = set()
            for snapshot in private_snapshots:
                private = unpack(snapshot,'private-session')
                team = private['team']
                check_team(team)
                if team in seen or private['public_sha256'] != digest:
                    raise InvalidData("Duplicate or mismatched private snapshot")
                seen.add(team)
                action = private['action']
                if action is not None:
                    if session.state.position.stage not in (Stage.SHIELDS,Stage.SWORDS):
                        raise InvalidData("Private choice outside a simultaneous stage")
                    session.act(team,action)
            return session
        except (KeyError,TypeError,ValueError) as exc:
            raise InvalidData(f"Invalid session: {exc}") from exc
