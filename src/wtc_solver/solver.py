"""Memoized backward induction. Stored values exclude completed matches."""
from fractions import Fraction as F
from itertools import product
from time import perf_counter
from types import MappingProxyType
from typing import TYPE_CHECKING
from .matrix_game import solve_matrix
from .models import Node, Stage, Team
from .payoff import Payoffs
from .rules import Rules

if TYPE_CHECKING:
    from .policy import Solution

def solve(payoffs: Payoffs | list | tuple, attacker_team: Team = "A") -> 'Solution':
    from .policy import Solution
    payoffs = payoffs if isinstance(payoffs, Payoffs) else Payoffs(payoffs)
    rules = Rules(attacker_team)
    nodes = {}
    matrices = {}
    stats = dict(cache_hits=0,cache_misses=0,terminal_evaluations=0,
                 matrix_nodes=0,matrix_games_solved=0,matrix_cache_hits=0)
    start = perf_counter()

    def visit(p):
        if p.stage == Stage.TERMINAL:
            stats['terminal_evaluations'] += 1
            return F(0)
        if p in nodes:
            stats['cache_hits'] += 1
            return nodes[p].value
        stats['cache_misses'] += 1
        actors = rules.actors(p)
        acts = [rules.legal_actions(p,t) for t in actors]
        values = []
        for actions in product(*acts):
            child,match = rules.transition(p,actions)
            values.append(visit(child)+(payoffs.gp(match) if match else 0))
        if len(actors) == 2:
            stats['matrix_nodes'] += 1
            width = len(acts[1])
            matrix = tuple(tuple(values[i:i+width]) for i in range(0,len(values),width))
            if matrix not in matrices:
                matrices[matrix] = solve_matrix(matrix)
                stats['matrix_games_solved'] += 1
            else:
                stats['matrix_cache_hits'] += 1
            r = matrices[matrix]
            node = Node(r.value,r.row,r.column)
        else:
            value = (max if actors[0] == 'A' else min)(values)
            count = values.count(value)
            probs = tuple(F(1,count) if v == value else F(0) for v in values)
            node = Node(value,probs if actors[0]=='A' else (),probs if actors[0]=='B' else ())
        nodes[p] = node
        return node.value

    visit(rules.initial().position)
    stats['solve_seconds'] = perf_counter()-start
    return Solution(payoffs,attacker_team,MappingProxyType(nodes),MappingProxyType(stats))
