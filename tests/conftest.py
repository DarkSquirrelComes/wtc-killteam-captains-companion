import pytest
from wtc_solver import Payoffs, solve
from wtc_solver.payoff import benchmark_payoffs

def tensor(fn):
    return Payoffs([[[[fn(a,b,t,m) for m in range(9)] for t in range(3)]
                     for b in range(3)] for a in range(3)])

@pytest.fixture(scope='session')
def fixed():
    return benchmark_payoffs()

@pytest.fixture(scope='session')
def complete(fixed):
    return {role:solve(fixed,role) for role in ('A','B')}

@pytest.fixture(scope='session')
def diagonal():
    return solve(tensor(lambda a,b,t,m:20 if a==b else 0))
