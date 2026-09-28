"""Exercise the public captain API for both roles, including deviations and restore.

Opponent choices below are synthetic test inputs, never a UI automation policy.
"""
import json
from pathlib import Path
from random import Random
from wtc_solver import load
from wtc_assistant.data import import_data
from wtc_assistant.solutions import PolicyBundle, calculate
from wtc_assistant.controller import CaptainController
from wtc_assistant.import_export import export_session, import_session

def main():
    config=import_data(Path('examples/captain_demo.csv').read_bytes(),'demo.csv')
    a,b=Path('outputs/policies/attacker_A.json'),Path('outputs/policies/attacker_B.json')
    bundle=(PolicyBundle.create(config,load(a,config.payoffs),load(b,config.payoffs))
            if a.exists() and b.exists() else calculate(config))
    results=[]
    for role in ('A','B'):
        c=CaptainController.start(bundle,role)
        restored=None
        rng=Random(20260928)
        deviations=0
        while c.view().mode!='complete':
            view=c.view()
            if restored is not None:
                assert restored.view()==view
            if view.mode=='own':
                proposal=c.propose_sample(rng)
                c.confirm_own(proposal.action,proposal.context)
                if restored is not None: restored.confirm_own(proposal.action,restored.context)
            else:
                rec=c.solution.get_recommendation(c.session.history,'B')
                action=next((a for a,p in zip(rec.actions,rec.probabilities) if p==0),rec.actions[-1])
                deviations+=int(rec.probabilities[rec.actions.index(action)]==0)
                c.record_opponent(action,view.context)
                if restored is not None: restored.record_opponent(action,restored.context)
            if restored is None and c.session.own_commitment is not None:
                restored=import_session(export_session(c.bundle,c.session))
                assert restored.view()==c.view()
        assert restored is not None and restored.view()==c.view()
        assert import_session(export_session(c.bundle,c.session)).view()==c.view()
        state=c.solution.get_state(c.session.history)
        assert len(state.matches)==3
        assert all(len({getattr(m,k) for m in state.matches})==3 for k in ('a','b','table','mission'))
        assert c.view().value.team_a+c.view().value.team_b==60
        assert deviations>0
        value=c.view().value
        history=list(c.view().history)
        c.rewind(1,c.context)
        assert len(c.session.history)==1 and c.session.own_commitment is None
        assert c.view().value==c.solution.get_value(c.session.history)
        results.append(dict(attacker=role,final_a=str(value.team_a),final_b=str(value.team_b),
                            non_equilibrium_inputs=deviations,public_decisions=history,
                            pending_restore_identical=True,complete_restore_identical=True,
                            undo_reconstructed=True))
    out=Path('outputs/captain-demo.json')
    out.write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    for r in results:
        print(f'Attacker {r["attacker"]}: GP {r["final_a"]}:{r["final_b"]}; '
              f'non-equilibrium choices {r["non_equilibrium_inputs"]}; restore and undo OK')

if __name__=='__main__': main()
