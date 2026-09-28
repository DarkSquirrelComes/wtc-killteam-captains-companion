from decimal import Decimal
from fractions import Fraction as F
import json
import pytest
from hypothesis import given,settings,strategies as st
from wtc_solver import InvalidData,Payoffs,load_payoffs
from wtc_solver.payoff import rational
from conftest import tensor

@pytest.mark.parametrize('value',[12.3,'12.3','123/10',Decimal('12.3'),F(123,10)])
def test_decimal_conversion(value):
    assert rational(value)==F(123,10)

@pytest.mark.parametrize('value',[True,None,complex(1,2),'nan','inf',float('inf'),'1/0',''])
def test_invalid_numbers(value):
    with pytest.raises(InvalidData): tensor(lambda *args:value)

@pytest.mark.parametrize('value',[-1,21,20.01])
def test_range(value):
    with pytest.raises(InvalidData): tensor(lambda *args:value)

def test_shape():
    with pytest.raises(InvalidData): Payoffs([])
    with pytest.raises(InvalidData): Payoffs([[[[10]*8]*3]*3]*3)

@settings(max_examples=30,deadline=None)
@given(st.lists(st.integers(0,200),min_size=243,max_size=243))
def test_random_tensor_constant_sum_and_symmetry(values):
    p=tensor(lambda a,b,t,m:F(values[((a*3+b)*3+t)*9+m],10))
    q=p.swapped()
    for a in range(3):
        for b in range(3):
            for t in range(3):
                for m in range(9): assert p.data[a][b][t][m]+q.data[b][a][t][m]==20
    assert q.swapped()==p

def test_json_and_csv_roundtrip(tmp_path,fixed):
    path=tmp_path/'data.json'; path.write_text(json.dumps(fixed.to_list()))
    assert load_payoffs(path)==fixed
    path=tmp_path/'data.csv'
    rows=['player_a,player_b,table,'+','.join(f'M{i}' for i in range(9))]
    for a in range(3):
        for b in range(3):
            for t in range(3): rows.append(','.join(map(str,[a,b,t,*fixed.data[a][b][t]])))
    path.write_text('\n'.join(rows))
    assert load_payoffs(path)==fixed
    blank=rows[1].split(','); blank[3]=''
    for bad in [rows[:-1],rows+[rows[1]],[rows[0],','.join(blank),*rows[2:]]]:
        path.write_text('\n'.join(bad))
        with pytest.raises(InvalidData): load_payoffs(path)

def test_blank_template_is_not_zero():
    with pytest.raises(InvalidData): tensor(lambda *args:'')
