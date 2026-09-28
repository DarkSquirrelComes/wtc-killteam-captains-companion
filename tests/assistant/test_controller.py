from dataclasses import replace
from fractions import Fraction as F
from random import Random
import pytest
from wtc_solver import Event, IllegalAction, Session, Stage
from wtc_assistant.controller import CaptainController, StaleDecision
from wtc_assistant.recommendations import percentages
from wtc_assistant.session import CaptainSession

def advance(controller, nonoptimal=False):
    view=controller.view()
    if view.mode=='own':
        controller.confirm_own(view.options[0].id, view.context)
    else:
        action=view.options[0].id
        if nonoptimal and view.mode=='opponent':
            rec=controller.solution.get_recommendation(controller.session.history,'B')
            action=next((a for a,p in zip(rec.actions,rec.probabilities) if p==0),action)
        controller.record_opponent(action,view.context)

@pytest.mark.parametrize('role',['A','B'])
def test_complete_controller_and_real_deviations(bundle,role):
    c=CaptainController.start(bundle,role)
    off_policy=False
    while c.view().mode!='complete':
        view=c.view()
        team='A' if view.mode=='own' else 'B'
        rec=c.solution.get_recommendation(c.session.history,team)
        assert tuple(x.id for x in view.options)==rec.actions
        if view.mode=='reveal':
            opponent=c.solution.get_recommendation(c.session.history,'B')
            expected=sum(p*c.solution.get_value(c.session.history+(Event((c.session.own_commitment,b)),)).team_a
                         for b,p in zip(opponent.actions,opponent.probabilities))
            assert view.value.team_a==expected
        else:
            assert view.value==c.solution.get_value(c.session.history)
        if team=='A':
            assert tuple(x.probability for x in view.options)==rec.probabilities
        else:
            assert all(x.probability is None for x in view.options)
            off_policy |= any(p==0 for p in rec.probabilities)
        advance(c,nonoptimal=True)
    assert off_policy
    state=c.solution.get_state(c.session.history)
    assert len(state.matches)==3
    for name in ('a','b','table','mission'):
        assert len({getattr(m,name) for m in state.matches})==3
    assert c.view().value.team_a+c.view().value.team_b==60
    assert sum(p.gp_a for p in c.view().pairs)==c.view().value.team_a
    assert all(p.gp_a+p.gp_b==20 for p in c.view().pairs)

@pytest.mark.parametrize('stage',[Stage.SHIELDS,Stage.SWORDS])
def test_hidden_opponent_action_cannot_enter_controller(bundle,stage):
    s=bundle.attacker_a
    h=(Event((8,)),Event((7,)))
    if stage==Stage.SWORDS: h += (Event((0,0)),)
    observed=[]
    for secret in s.rules.legal_actions(s.get_state(h).position,'B'):
        # The game engine can hold an opponent secret. The assistant receives
        # ONLY its public history, never its private export or internal state.
        external=Session(s,h)
        external.act('B',secret)
        c=CaptainController(bundle,CaptainSession('A',external.history,session_id='test'))
        observed.append(c.view())
        with pytest.raises(IllegalAction): c.record_opponent(secret,c.context)
    assert all(v==observed[0] for v in observed)

def test_sampling_requires_confirmation_and_does_not_mutate(bundle):
    c=CaptainController.start(bundle,'B')  # Our defender ban.
    state=c.session; policy=c.solution.nodes
    p1=c.propose_sample(Random(9)); p2=c.propose_sample(Random(9))
    assert p1==p2 and c.session==state and c.solution.nodes is policy
    c.confirm_own(p1.action,p1.context)
    with pytest.raises(StaleDecision): c.confirm_own(p2.action,p2.context)
    with pytest.raises(IllegalAction): c.propose_sample(Random(9))

def test_history_correction_invalidates_every_later_decision(bundle):
    c=CaptainController.start(bundle,'A')
    while len(c.session.history)<7: advance(c)
    obsolete=c.view()
    c.rewind(1,c.context)
    assert len(c.session.history)==1
    assert c.session.own_commitment is None
    with pytest.raises(StaleDecision): c.confirm_own(obsolete.options[0].id,obsolete.context)
    advance(c)
    assert len(c.session.history)==2
    c.confirm_own(1,c.context)
    assert c.session.own_commitment==1
    c.undo(c.context)
    assert c.session.own_commitment is None and len(c.session.history)==2
    c.undo(c.context)
    assert len(c.session.history)==1
    assert c.view().value==c.solution.get_value(c.session.history)

def test_label_rename_preserves_exact_policy_and_identity(bundle):
    c=CaptainController.start(bundle,'A')
    old=c.context; solution=c.solution
    names=replace(bundle.config.names,players_a=('Алексей','Борис','Виктор'))
    c.rename(names,c.context)
    assert c.solution is solution
    assert c.bundle.config.payoffs==bundle.config.payoffs
    assert c.context!=old

def test_invalid_history_and_actor(bundle):
    c=CaptainController.start(bundle,'A')
    with pytest.raises(IllegalAction): c.confirm_own(0,c.context)
    with pytest.raises(IllegalAction): c.undo(c.context)
    with pytest.raises(IllegalAction): c.record_opponent(99,c.context)
    with pytest.raises(IllegalAction): c.rewind(-1,c.context)
    with pytest.raises(IllegalAction): CaptainController(bundle,CaptainSession('A',own_commitment=0,session_id='x'))

def test_restored_branches_with_same_revision_have_distinct_contexts(bundle):
    first=CaptainController(bundle,CaptainSession('A',(Event((0,)),),revision=1,session_id='same'))
    second=CaptainController(bundle,CaptainSession('A',(Event((1,)),),revision=1,session_id='same'))
    assert first.context!=second.context
    with pytest.raises(StaleDecision): second.confirm_own(2,first.context)

def test_percentage_rounding_preserves_sum_and_zero_support():
    p=(F(1,3),F(1,3),F(1,3),F(0))
    strings=percentages(p)
    assert strings==('33.4%','33.3%','33.3%','0.0%')
    assert sum(F(x[:-1]) for x in strings)==100
