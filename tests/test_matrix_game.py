from fractions import Fraction as F
import pytest
from hypothesis import given, settings, strategies as st
from wtc_solver.matrix_game import solve_matrix
from wtc_solver.verify import verify_matrix

@pytest.mark.parametrize('matrix,value,p,q',[
    ([[1,-1],[-1,1]],0,[F(1,2)]*2,[F(1,2)]*2),
    ([[0,-1,1],[1,0,-1],[-1,1,0]],0,[F(1,3)]*3,[F(1,3)]*3),
    ([[3,2],[1,0]],2,[1,0],[0,1]),
    ([[2,0],[0,1]],F(2,3),[F(1,3),F(2,3)],[F(1,3),F(2,3)]),
    ([[2,0,0],[0,3,0],[0,0,6]],1,[F(1,2),F(1,3),F(1,6)],[F(1,2),F(1,3),F(1,6)]),
    ([[1,-1,3],[-1,1,3],[-2,-2,0]],0,[F(1,2),F(1,2),0],[F(1,2),F(1,2),0]),
    ([[5,5],[5,5]],5,[F(1,2)]*2,[F(1,2)]*2),
    ([[1,-1],[-1,1],[1,-1]],0,[F(1,4),F(1,2),F(1,4)],[F(1,2)]*2),
    ([[0,0,0],[0,0,0],[0,0,0]],0,[F(1,3)]*3,[F(1,3)]*3),
    ([[1,1],[1,0]],1,[1,0],[F(1,2)]*2),
    ([[3]],3,[1],[1]),
])
def test_known_games(matrix,value,p,q):
    r=solve_matrix(matrix)
    assert (r.value,r.row,r.column)==(value,tuple(p),tuple(q))
    assert r.residual==0
    verify_matrix(matrix,r.row,r.column,r.value)
    assert solve_matrix(matrix)==r

@settings(max_examples=70,deadline=None)
@given(st.lists(st.integers(-10,10),min_size=9,max_size=9))
def test_random_exact_certificates(values):
    m=[values[i:i+3] for i in (0,3,6)]
    r=solve_matrix(m)
    verify_matrix(m,r.row,r.column,r.value)
    dual=solve_matrix([[-m[i][j] for i in range(3)] for j in range(3)])
    assert (dual.value,dual.row,dual.column)==(-r.value,r.column,r.row)

@pytest.mark.parametrize('matrix',[[],[[]],[[1,2],[3]],[[0]*4]*2,[[0]]*4])
def test_invalid_shape(matrix):
    with pytest.raises(ValueError):
        solve_matrix(matrix)

def test_certificate_rejects_profitable_deviations():
    with pytest.raises(ValueError):
        verify_matrix([[1,-1],[-1,1]],(1,0),(1,0),1)
