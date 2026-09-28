"""Independent certificate checks: no optimizer or backward-induction calls.

Reconstructs reachable edges using the public rules, tests every stored
matrix inequality and every sequential Bellman equation, and rejects orphan
or missing nodes. Separate tests independently exercise the rules themselves.
"""
from fractions import Fraction as F
from itertools import product
from .models import Stage

def require(condition, message):
    if not condition:
        raise ValueError(message)

def verify_matrix(matrix,p,q,v):
    require(len(p)==len(matrix) and len(q)==len(matrix[0]),'Distribution dimensions')
    for distribution in (p,q):
        require(sum(distribution)==1 and all(x>=0 for x in distribution),'Invalid distribution')
    require(all(sum(x*y for x,y in zip(row,q))<=v for row in matrix),'Profitable row deviation')
    require(all(sum(p[i]*matrix[i][j] for i in range(len(p)))>=v for j in range(len(q))),
            'Profitable column deviation')
    require(sum(p[i]*q[j]*matrix[i][j] for i in range(len(p)) for j in range(len(q)))==v,
            'Expected value mismatch')

def verify_solution(solution):
    rules = solution.rules
    seen = set()
    stack = [rules.initial().position]
    counts = dict(sequential_nodes=0,matrix_nodes=0,terminal_edges=0)
    while stack:
        p = stack.pop()
        if p in seen:
            continue
        seen.add(p)
        require(p in solution.nodes,'Missing reachable policy node')
        node = solution.nodes[p]
        actors = rules.actors(p)
        acts = [rules.legal_actions(p,t) for t in actors]
        values=[]
        for actions in product(*acts):
            child,match = rules.transition(p,actions)
            reward = solution.payoffs.gp(match) if match else F(0)
            if child.stage == Stage.TERMINAL:
                values.append(reward)
                counts['terminal_edges']+=1
            else:
                require(child in solution.nodes,'Missing continuation')
                values.append(reward+solution.nodes[child].value)
                stack.append(child)
        if len(actors)==2:
            width=len(acts[1])
            matrix=[values[i:i+width] for i in range(0,len(values),width)]
            verify_matrix(matrix,node.a,node.b,node.value)
            counts['matrix_nodes']+=1
        else:
            actor=actors[0]
            probs=node.a if actor=='A' else node.b
            require(not (node.b if actor=='A' else node.a),'Non-actor strategy is nonempty')
            optimum=(max if actor=='A' else min)(values)
            require(node.value==optimum,'Bellman value mismatch')
            require(len(probs)==len(values),'Wrong action count')
            count=values.count(optimum)
            expected=tuple(F(1,count) if v==optimum else F(0) for v in values)
            require(probs==expected,'Nonoptimal or nonuniform sequential strategy')
            counts['sequential_nodes']+=1
    require(seen==set(solution.nodes),'Unreachable extra policy nodes')
    return counts
