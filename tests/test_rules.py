from functools import lru_cache
from itertools import product
import pytest
from hypothesis import given,settings,strategies as st
from wtc_solver import Event,IllegalAction,Rules,Stage

@pytest.mark.parametrize('role',['A','B'])
def test_order_resources_and_matchups(role):
    r=Rules(role)
    s=r.initial()
    defender='B' if role=='A' else 'A'
    expected=[(defender,),(role,),('A','B'),('A','B'),(role,),(defender,),
              (defender,),(role,),(defender,)]
    actions=[(8,),(7,),(0,1),(2,2),(2,),(6,),(0,),(5,),(4,)]
    for stage,(actors,act) in enumerate(zip(expected,actions)):
        assert s.position.stage==stage
        assert r.actors(s.position)==actors
        for t in ('A','B'):
            if t not in actors:
                assert r.legal_actions(s.position,t)==()
        s=r.apply(s,Event(act))
        if stage==3:
            assert s.position.pairs==(((2,1),(0,2),(1,0)) if role=='A' else ((0,2),(2,1),(1,0)))
        if stage==5:
            assert s.position.tables==(0,1)
            assert s.position.missions==tuple(range(6))
    assert s.position.stage==Stage.TERMINAL
    assert s.position.tables==()
    assert s.position.missions==(0,1,2,3)
    assert [m.table for m in s.matches]==[2,0,1]
    assert [m.mission for m in s.matches]==[6,5,4]
    assert {m.a for m in s.matches}=={0,1,2}
    assert {m.b for m in s.matches}=={0,1,2}
    with pytest.raises(IllegalAction):
        r.apply(s,Event((0,)))

@pytest.mark.parametrize('role',['A','B'])
def test_illegal_actions_at_every_stage(role):
    r=Rules(role)
    s=r.initial()
    while s.position.stage!=Stage.TERMINAL:
        actors=r.actors(s.position)
        legal=tuple(r.legal_actions(s.position,t)[0] for t in actors)
        for bad in [(),(99,)*len(actors),(True,)*len(actors),(0.0,)*len(actors),legal+(0,)]:
            with pytest.raises(IllegalAction):
                r.apply(s,Event(bad))
        s=r.apply(s,Event(legal))

def test_repeated_ban_and_selected_shield_illegal():
    r=Rules()
    s=r.apply(r.initial(),Event((0,)))
    with pytest.raises(IllegalAction): r.apply(s,Event((0,)))
    s=r.apply(s,Event((1,)))
    s=r.apply(s,Event((0,2)))
    with pytest.raises(IllegalAction): r.apply(s,Event((2,1)))
    with pytest.raises(IllegalAction): r.legal_actions(s.position,'X')
    with pytest.raises(IllegalAction): Rules('X')

@settings(max_examples=120,deadline=None)
@given(st.sampled_from(['A','B']),st.lists(st.integers(0,1000),min_size=11,max_size=11))
def test_random_complete_histories(role,draws):
    r=Rules(role); s=r.initial(); k=0; history=[]
    while s.position.stage!=Stage.TERMINAL:
        actions=[]
        for t in r.actors(s.position):
            legal=r.legal_actions(s.position,t)
            actions.append(legal[draws[k]%len(legal)]); k+=1
        event=Event(tuple(actions)); history.append(event)
        s=r.apply(s,event)
    assert r.replay(history)==s
    assert len(s.matches)==3
    for attr in ('a','b','table','mission'):
        assert len({getattr(m,attr) for m in s.matches})==3

@pytest.mark.parametrize('role',['A','B'])
def test_exhaustive_action_sequence_count(role):
    r=Rules(role)
    @lru_cache(None)
    def count(p):
        if p.stage==Stage.TERMINAL: return 1
        return sum(count(r.transition(p,a)[0]) for a in product(*(r.legal_actions(p,t) for t in r.actors(p))))
    assert count(r.initial().position)==3265920
