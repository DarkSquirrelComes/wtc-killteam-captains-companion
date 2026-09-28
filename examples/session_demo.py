"""Complete session using only the public API; verify the same after reload."""
from pathlib import Path
from random import Random
from wtc_solver import Session,Stage,solve,sample_action,save,load
from wtc_solver.payoff import benchmark_payoffs

def run(solution):
    rng=Random(20260928)
    session=Session(solution)
    trace=[]
    while session.state.position.stage!=Stage.TERMINAL:
        for team in solution.rules.actors(session.state.position):
            rec=session.recommendation(team)
            action=sample_action(rec,rng)
            trace.append(rec)
            session.act(team,action)
    return session,trace

def main():
    out=Path('outputs/policies'); out.mkdir(parents=True,exist_ok=True)
    for attacker in ('A','B'):
        path=out/f'attacker_{attacker}.json'
        solution=load(path) if path.exists() else solve(benchmark_payoffs(),attacker)
        first,trace=run(solution)
        save(solution,path)
        restored=load(path,solution.payoffs)
        second,again=run(restored)
        assert trace==again and first.state==second.state and first.history==second.history
        assert Session.restore(restored,first.export()).state==first.state
        print(f'Attacker {attacker}: root A GP = {solution.get_value().team_a}')
        for event,stage in zip(first.history,Stage):
            print(f'  {stage.name}: {event.actions}')
        print('  Match assignments:',first.state.matches)
        print('  Final expected GP:',solution.get_value(first.history))
        print('  Reload: identical recommendations and session')

if __name__=='__main__': main()
