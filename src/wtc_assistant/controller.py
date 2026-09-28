"""Single-captain controller. Never receives or stores an unrevealed opponent action."""
from dataclasses import replace
import hashlib
import json
from typing import Callable
from wtc_solver import Event, GameValue, IllegalAction, Stage, sample_action
from .config import Names
from .recommendations import ActionOption, DecisionView, PairView, ResourceView, STAGE_TITLES, percentages
from .session import CaptainSession, Proposal
from .solutions import PolicyBundle

class StaleDecision(IllegalAction):
    """The view/proposal belongs to an obsolete history or configuration."""

class CaptainController:
    def __init__(self, bundle: PolicyBundle, session: CaptainSession,
                 persist: Callable[[PolicyBundle, CaptainSession], None] | None = None):
        self._bundle = bundle
        self._session = session
        self._persist = persist
        self._validate(session)

    @classmethod
    def start(cls, bundle, attacker_team, persist=None):
        controller = cls(bundle, CaptainSession.new(attacker_team), persist)
        if persist: persist(bundle, controller._session)
        return controller

    @property
    def bundle(self): return self._bundle

    @property
    def session(self): return self._session

    @property
    def solution(self): return self._bundle.solution(self._session.attacker_team)

    @property
    def context(self):
        # Revision alone can collide when two exported branches are restored.
        payload = [self._session.attacker_team, [e.actions for e in self._session.history],
                   self._session.own_commitment, self._bundle.config.payoffs.fingerprint,
                   self._bundle.config.names.to_data()]
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
        return f'{self._session.session_id}:{self._session.revision}:{digest}'

    def _validate(self, session):
        solution = self._bundle.solution(session.attacker_team)
        p = solution.get_state(session.history).position
        if type(session.revision) is not int or session.revision < 0 or not isinstance(session.session_id, str) or not session.session_id:
            raise IllegalAction('Повреждён идентификатор или версия сессии.')
        if session.own_commitment is not None:
            legal = solution.rules.legal_actions(p, 'A')
            if p.stage not in (Stage.SHIELDS, Stage.SWORDS) or type(session.own_commitment) is not int or session.own_commitment not in legal:
                raise IllegalAction('Недопустимый сохранённый выбор нашего капитана.')

    def _check(self, context):
        if context != self.context:
            raise StaleDecision('История изменилась. Используйте новую рекомендацию.')

    def _change(self, **changes):
        candidate = replace(self._session, revision=self._session.revision+1, **changes)
        self._validate(candidate)
        # Commit in memory only after the durable write succeeds.
        if self._persist: self._persist(self._bundle, candidate)
        self._session = candidate

    def _name(self, stage, team, action):
        names = self._bundle.config.names
        if stage == Stage.SHIELDS:
            return (names.players_a if team == 'A' else names.players_b)[action]
        if stage == Stage.SWORDS:
            return (names.players_b if team == 'A' else names.players_a)[action]
        if stage in (Stage.DEFENDER_TABLE, Stage.ATTACKER_TABLE):
            return names.tables[action]
        return names.missions[action]

    def view(self) -> DecisionView:
        session, solution = self._session, self.solution
        state = solution.get_state(session.history)
        p = state.position
        actors = solution.rules.actors(p)
        simultaneous = len(actors) == 2
        mode = ('complete' if not actors else 'reveal' if session.own_commitment is not None
                else 'own' if 'A' in actors else 'opponent')
        team = 'A' if mode == 'own' else 'B'
        rec = solution.get_recommendation(session.history, team)
        values = solution.get_action_values(session.history, 'A') if mode == 'own' else ()
        display = percentages(rec.probabilities) if mode == 'own' else ()
        options = tuple(ActionOption(a, self._name(p.stage, team, a),
                       rec.probabilities[i] if mode == 'own' else None,
                       display[i] if display else None,
                       values[i].expected_a if values else None,
                       values[i].guarantee_for_team if values else None)
                       for i,a in enumerate(rec.actions)) if actors else ()
        names = self._bundle.config.names
        pairs = [PairView(names.players_a[m.a], names.players_b[m.b], names.tables[m.table],
                          names.missions[m.mission], solution.payoffs.gp(m), 20-solution.payoffs.gp(m))
                 for m in state.matches]
        for i,(a,b) in enumerate(p.pairs):
            selected = p.table if i == 0 and p.table != -1 else p.tables[0] if len(p.tables) == 1 else None
            pairs.append(PairView(names.players_a[a], names.players_b[b],
                                 names.tables[selected] if selected is not None else None, None, None, None))
        assigned_m = {m.mission for m in state.matches}
        assigned_t = {m.table for m in state.matches}
        banned = set(range(len(names.missions))) - set(p.missions) - assigned_m
        missions = tuple(ResourceView(n, 'Назначена' if i in assigned_m else 'Забанена' if i in banned else 'Доступна')
                         for i,n in enumerate(names.missions))
        tables = tuple(ResourceView(n, 'Назначен' if i in assigned_t else 'Выбран' if i == p.table else 'Доступен')
                       for i,n in enumerate(names.tables))
        shields = None
        history = []
        for i,e in enumerate(session.history):
            before = solution.get_state(session.history[:i]).position
            if before.stage == Stage.SHIELDS:
                a,b = e.actions
                shields = (names.players_a[a], names.players_b[b])
            entries = [f'{"Мы" if t == "A" else "Соперник"}: {self._name(before.stage,t,a)}'
                       for t,a in zip(solution.rules.actors(before),e.actions)]
            history.append(f'{STAGE_TITLES[before.stage]} — ' + '; '.join(entries))
        explanation = ('Это одна выбранная равновесная стратегия. Вероятности сохранены решателем.'
                       ' Положительные действия оптимальны против равновесной смеси соперника;'
                       ' отдельный чистый ход не обязательно сохраняет гарантию смеси.' if simultaneous else
                       'Действия с положительной вероятностью равноценны при оптимальной дальнейшей игре.')
        value = solution.get_value(session.history)
        if session.own_commitment is not None:
            chosen = next(x for x in solution.get_action_values(session.history, 'A') if x.action == session.own_commitment)
            value = GameValue(chosen.expected_a, 60-chosen.expected_a, value.accrued_a, chosen.expected_a-value.accrued_a)
        return DecisionView(self.context, p.stage, STAGE_TITLES[p.stage], mode,
                            'Атакующий' if session.attacker_team == 'A' else 'Защитник', options,
                            value, simultaneous,
                            self._name(p.stage,'A',session.own_commitment) if session.own_commitment is not None else None,
                            tuple(pairs), missions, tables, shields, tuple(history), explanation)

    def propose_sample(self, rng) -> Proposal:
        if self.view().mode != 'own':
            raise IllegalAction('Случайный выбор доступен только для нашего неподтверждённого хода.')
        rec = self.solution.get_recommendation(self._session.history, 'A')
        return Proposal(sample_action(rec, rng), self.context, True)

    def confirm_own(self, action: int, context: str):
        self._check(context)
        if self.view().mode != 'own': raise IllegalAction('Сейчас ожидается другой участник.')
        p = self.solution.get_state(self._session.history).position
        if type(action) is not int or action not in self.solution.rules.legal_actions(p, 'A'):
            raise IllegalAction('Недопустимый выбор.')
        if len(self.solution.rules.actors(p)) == 2:
            self._change(own_commitment=action)
        else:
            self._change(history=self._session.history+(Event((action,)),))

    def record_opponent(self, revealed_action: int, context: str):
        """Only call after the physical opponent decision has been REVEALED."""
        self._check(context)
        mode = self.view().mode
        if mode not in ('opponent', 'reveal'):
            raise IllegalAction('Сначала подтвердите собственный скрытый выбор.')
        actions = (self._session.own_commitment, revealed_action) if mode == 'reveal' else (revealed_action,)
        history = self._session.history + (Event(actions),)
        self.solution.get_state(history)  # All game legality delegated to rules.
        self._change(history=history, own_commitment=None)

    def undo(self, context: str):
        self._check(context)
        if self._session.own_commitment is not None: self._change(own_commitment=None)
        elif self._session.history: self._change(history=self._session.history[:-1])
        else: raise IllegalAction('Нет решений для отмены.')

    def rewind(self, keep_events: int, context: str):
        """Discard EVERY event after the specified public-history prefix."""
        self._check(context)
        if type(keep_events) is not int or not 0 <= keep_events <= len(self._session.history):
            raise IllegalAction('Недопустимая точка возврата.')
        self._change(history=self._session.history[:keep_events], own_commitment=None)

    def rename(self, names: Names, context: str):
        self._check(context)
        bundle = self._bundle.renamed(names)
        session = replace(self._session, revision=self._session.revision+1)
        if self._persist: self._persist(bundle, session)
        self._bundle, self._session = bundle, session
