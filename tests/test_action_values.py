from fractions import Fraction as F
import pytest
from wtc_solver import Event

@pytest.mark.parametrize('team', ['A','B'])
def test_simultaneous_action_values_and_guarantees(diagonal, team):
    history = (Event((8,)), Event((7,)), Event((0,0)))
    values = diagonal.get_action_values(history, team)
    assert [v.expected_a for v in values] == [10,10]
    assert [v.guarantee_for_team for v in values] == ([0,0] if team=='A' else [40,40])
    assert all(v.against_equilibrium_mix for v in values)

def test_sequential_values_use_actual_child_and_accrued_score(complete):
    s = complete['A']
    assert s.get_action_values((), 'A') == ()
    for v in s.get_action_values((), 'B'):
        assert v.expected_a == s.get_value((Event((v.action,)),)).team_a
        assert v.guarantee_for_team == 60-v.expected_a
        assert not v.against_equilibrium_mix
