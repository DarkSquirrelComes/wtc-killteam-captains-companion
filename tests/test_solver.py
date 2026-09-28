from fractions import Fraction as F
import pytest
from wtc_solver import Event,solve,Stage
from wtc_solver.verify import verify_solution
from conftest import tensor
from oracle import allocations,sword_matrix,two_by_two

@pytest.mark.full
@pytest.mark.parametrize('role',['A','B'])
def test_all_stored_certificates(complete,role):
    s=complete[role]
    counts=verify_solution(s)
    assert counts['matrix_nodes']==360
    assert counts['terminal_edges']>0
    assert s.statistics['cache_hits']>0
    assert s.statistics['cache_misses']==len(s.nodes)
    assert s.get_value().team_a+s.get_value().team_b==60

@pytest.mark.parametrize('role',['A','B'])
def test_independent_exhaustive_oracle(complete,fixed,role):
    s=complete[role]
    history=(Event((8,)),Event((7,)),Event((0,1)))
    expected_matrix=sword_matrix(fixed.data,0,1,tuple(range(7)),role)
    assert s.get_value(history).team_a==two_by_two(expected_matrix)
    for ib,b in enumerate((0,2)):
        for ia,a in enumerate((1,2)):
            h=history+(Event((b,a)),)
            assert s.get_value(h).team_a==expected_matrix[ib][ia]

def test_analytical_sword_and_shield_mixing(diagonal):
    # If shields have the same index: sword matrix [[20,0],[0,20]], value 10.
    # If different: a saddle at value 20. Thus shield matrix has 10 on the
    # diagonal, 20 elsewhere; its unique equilibrium is uniform, value 50/3.
    h=(Event((8,)),Event((7,)))
    assert diagonal.get_value(h).team_a==F(50,3)
    for team in ('A','B'):
        assert diagonal.get_recommendation(h,team).probabilities==(F(1,3),)*3
        assert diagonal.get_recommendation(h+(Event((0,0)),),team).probabilities==(F(1,2),)*2
    assert diagonal.get_value(h+(Event((0,0)),)).team_a==10

def test_all_ties():
    s=solve(tensor(lambda a,b,t,m:'10.1'))
    assert s.get_value().team_a==F(303,10)
    assert s.get_recommendation((),'B').probabilities==(F(1,9),)*9
    for p,node in s.nodes.items():
        for team,probs in [('A',node.a),('B',node.b)]:
            n=len(s.rules.legal_actions(p,team))
            assert probs==((F(1,n),)*n if n else ())

def test_uniquely_optimal_bans_and_off_path_continuation():
    # All missions score 10, except M8=20 and M7=0. Defender B must ban M8;
    # attacker A then bans M7. If B instead bans M0, A still bans M7 and B
    # cannot stop A taking M8 for its Shield: total 40, not root value 30.
    s=solve(tensor(lambda a,b,t,m:20 if m==8 else 0 if m==7 else 10))
    assert s.get_recommendation((),'B').probabilities==(F(0),)*8+(F(1),)
    h=(Event((8,)),)
    assert s.get_recommendation(h,'A').probabilities==(F(0),)*7+(F(1),)
    assert s.get_value().team_a==30
    assert s.get_value((Event((0,)),)).team_a==40

def test_uniquely_optimal_table():
    # Only A0 can score; its chosen opponent and mission do not matter.
    # With A0 in Defender B's Shield match, Attacker A must select table 2.
    s=solve(tensor(lambda a,b,t,m:20 if a==0 and t==2 else 0))
    h=(Event((8,)),Event((7,)),Event((1,0)),Event((1,0)))
    rec=s.get_recommendation(h,'A')
    assert rec.stage==Stage.DEFENDER_TABLE
    assert rec.probabilities==(0,0,1)
    assert rec.value.team_a==20

def test_equivalent_histories_and_accrued_score(complete):
    s=complete['A']
    h1=(Event((0,)),Event((1,)))
    h2=(Event((1,)),Event((0,)))
    assert s.get_state(h1).position==s.get_state(h2).position
    assert s.get_recommendation(h1,'A')==s.get_recommendation(h2,'A')
    # Same future pair, table, remaining missions; different completed allocations.
    base=(Event((8,)),Event((7,)),Event((0,1)),Event((2,2)))
    x=base+(Event((0,)),Event((0,)),Event((1,)),Event((1,)))
    y=base+(Event((1,)),Event((1,)),Event((0,)),Event((0,)))
    assert s.get_state(x).position==s.get_state(y).position
    vx,vy=s.get_value(x),s.get_value(y)
    assert vx.remaining_a==vy.remaining_a
    assert vx.team_a-vy.team_a==vx.accrued_a-vy.accrued_a

@pytest.mark.parametrize('role',['A','B'])
def test_role_swap_symmetry(complete,fixed,role):
    opposite='B' if role=='A' else 'A'
    swapped=solve(fixed.swapped(),opposite)
    assert complete[role].get_value().team_a+swapped.get_value().team_a==60
