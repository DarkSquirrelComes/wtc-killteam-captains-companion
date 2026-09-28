"""Exact LP vertex enumeration for small zero-sum games, including degeneracy.

Enumerate vertices of {p>=0, sum(p)=1, M^T p>=v}. At the maximal
v its vertices are precisely the extreme optimal row strategies. Average
ALL distinct optimal vertices, then repeat for -M^T for the column player.
This yields the union of all optimal supports, deterministically.
"""
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import combinations
from .payoff import rational

@dataclass(frozen=True, slots=True)
class MatrixResult:
    value: F
    row: tuple[F, ...]
    column: tuple[F, ...]
    row_vertices: int
    column_vertices: int
    residual: F = F(0)

def linear_solve(rows, rhs):
    """Exact Gauss-Jordan; None means singular, including redundant constraints."""
    n = len(rhs)
    a = [list(map(F,r))+[F(b)] for r,b in zip(rows,rhs)]
    for j in range(n):
        pivot = next((i for i in range(j,n) if a[i][j]), None)
        if pivot is None:
            return None
        a[j],a[pivot] = a[pivot],a[j]
        v = a[j][j]
        a[j] = [x/v for x in a[j]]
        for i in range(n):
            if i != j and a[i][j]:
                c = a[i][j]
                a[i] = [x-c*y for x,y in zip(a[i],a[j])]
    return tuple(r[-1] for r in a)

def optimal_vertices(m):
    n,k = len(m),len(m[0])
    constraints = [tuple(F(i==j) for i in range(n))+(F(0),) for j in range(n)]
    constraints += [tuple(m[i][j] for i in range(n))+(F(-1),) for j in range(k)]
    best = None
    vertices = set()
    for active in combinations(constraints,n):
        x = linear_solve([(F(1),)*n+(F(0),), *active], [1]+[0]*n)
        if x is None or any(z < 0 for z in x[:-1]):
            continue
        if any(sum(c*y for c,y in zip(row,x)) < 0 for row in constraints[n:]):
            continue
        if best is None or x[-1] > best:
            best,vertices = x[-1],{x[:-1]}
        elif x[-1] == best:
            vertices.add(x[:-1])
    if best is None:
        raise ArithmeticError("Bounded finite game has no optimal vertex")
    ordered = sorted(vertices)
    mean = tuple(sum(p[i] for p in ordered)/len(ordered) for i in range(n))
    return best,mean,len(ordered)

def solve_matrix(matrix) -> MatrixResult:
    m = tuple(tuple(rational(x) for x in row) for row in matrix)
    if not 1 <= len(m) <= 3 or not m or not 1 <= len(m[0]) <= 3 or any(len(r)!=len(m[0]) for r in m):
        raise ValueError("Expected a rectangular 1..3 by 1..3 matrix")
    v,p,np = optimal_vertices(m)
    w,q,nq = optimal_vertices(tuple(tuple(-m[i][j] for i in range(len(m))) for j in range(len(m[0]))))
    if v != -w:
        raise ArithmeticError("Primal/dual values disagree")
    return MatrixResult(v,p,q,np,nq)
