"""Deliberately exhaustive reference, independent of production rules/optimizer.

Accepts a fixed ordered pairing after simultaneous decisions. Enumerates every
table/mission leaf without memoization. No calls to wtc_solver are made.
"""
from fractions import Fraction as F

def two_by_two(m):
    a,b=m[0]; c,d=m[1]
    lower=max(min(a,b),min(c,d))
    upper=min(max(a,c),max(b,d))
    if lower==upper: return lower
    return F(a*d-b*c,a-b-c+d)

def allocations(data,pairs,missions,attacker):
    attack=max if attacker=='A' else min
    defend=min if attacker=='A' else max
    def payoff(k,t,m):
        a,b=pairs[k]
        return data[a][b][t][m]
    return attack(defend(payoff(0,t0,m0)+defend(
        attack(payoff(1,t1,m1)+defend(payoff(2,3-t0-t1,m2)
            for m2 in missions if m2 not in (m0,m1))
            for m1 in missions if m1!=m0)
        for t1 in range(3) if t1!=t0)
        for m0 in missions) for t0 in range(3))

def sword_matrix(data,sa,sb,missions,attacker):
    matrix=[]
    for b in range(3):
        if b==sb: continue
        row=[]
        for a in range(3):
            if a==sa: continue
            pa,pb=(sa,b),(a,sb)
            pairs=(pb,pa,(3-sa-a,3-sb-b)) if attacker=='A' else (pa,pb,(3-sa-a,3-sb-b))
            row.append(allocations(data,pairs,missions,attacker))
        matrix.append(row)
    return matrix
