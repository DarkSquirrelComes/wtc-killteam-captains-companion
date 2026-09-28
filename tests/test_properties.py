from fractions import Fraction as F
from hypothesis import given,settings,strategies as st
from wtc_solver import Event,Stage,solve
from wtc_solver.verify import verify_solution
from conftest import tensor
from oracle import allocations

@settings(max_examples=3,deadline=None,derandomize=True)
@given(st.lists(st.integers(0,20),min_size=243,max_size=243),
       st.sampled_from(['A','B']),st.lists(st.integers(0,100),min_size=11,max_size=11))
def test_random_full_games_and_off_policy_paths(values,role,draws):
    p=tensor(lambda a,b,t,m:values[((a*3+b)*3+t)*9+m])
    s=solve(p,role)
    verify_solution(s)
    swapped=solve(p.swapped(),'B' if role=='A' else 'A')
    assert s.get_value().team_a+swapped.get_value().team_a==60
    h=(); k=0
    while s.get_state(h).position.stage!=Stage.TERMINAL:
        state=s.get_state(h)
        if state.position.stage==Stage.DEFENDER_TABLE:
            assert s.get_value(h).remaining_a==allocations(p.data,state.position.pairs,state.position.missions,role)
        actions=[]
        for team in s.rules.actors(state.position):
            rec=s.get_recommendation(h,team)
            assert sum(rec.probabilities)==1
            assert all(x>=0 for x in rec.probabilities)
            actions.append(rec.actions[draws[k]%len(rec.actions)]); k+=1
        h=h+(Event(tuple(actions)),)
        v=s.get_value(h)
        assert v.team_a+v.team_b==60
        assert v.team_a==v.accrued_a+v.remaining_a
    assert s.get_value(h).remaining_a==F(0)
