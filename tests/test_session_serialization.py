from dataclasses import replace
from fractions import Fraction as F
from random import Random
import json
import pytest
from wtc_solver import Event,IllegalAction,InvalidData,Session,Stage,sample_action
from wtc_solver.serialization import dumps,loads,pack,unpack

def play(solution,seed=21):
    session=Session(solution); rng=Random(seed); recommendations=[]
    while session.state.position.stage!=Stage.TERMINAL:
        for team in solution.rules.actors(session.state.position):
            rec=session.recommendation(team)
            recommendations.append(rec)
            session.act(team,sample_action(rec,rng))
    return session,recommendations

@pytest.mark.parametrize('role',['A','B'])
def test_roundtrip_all_nodes_and_full_session(complete,role):
    s=complete[role]
    encoded=dumps(s)
    restored=loads(encoded,s.payoffs)
    assert restored.nodes==s.nodes
    assert restored.get_value()==s.get_value()
    assert dumps(restored)==encoded
    first,recs=play(s); second,recs2=play(restored)
    assert recs2==recs
    assert first.history==second.history
    assert first.state==second.state
    assert Session.restore(restored,first.export()).state==first.state
    value=restored.get_value(second.history)
    assert value.remaining_a==0
    assert value.team_a==sum(s.payoffs.gp(m) for m in second.state.matches)
    for team in ('A','B'): assert second.recommendation(team).actions==()

def test_hidden_choices_do_not_leak_and_private_roundtrip(complete):
    s=complete['A']; h=(Event((8,)),Event((7,)))
    first,second=Session(s,h),Session(s,h)
    first.act('A',0); second.act('A',2)
    assert first.state==second.state
    assert first.history==second.history
    assert first.recommendation('B')==second.recommendation('B')
    assert first.export()==second.export()
    assert first.export_private('B')==second.export_private('B')
    restored=Session.restore(s,first.export(),[first.export_private('A'),first.export_private('B')])
    assert restored.act('B',1)==Event((0,1))
    assert first.act('B',1)==Event((0,1))
    assert restored.state==first.state
    # The next simultaneous stage must also ignore private opposing choices.
    before=first.recommendation('A')
    first.act('B',1)
    assert first.recommendation('A')==before

def test_undo_and_alternative_continuations(complete):
    session=Session(complete['A'])
    session.act('B',8); session.act('A',7)
    prior=session.history
    session.act('A',0); session.undo()
    assert session.history==prior
    session.act('A',2); session.act('B',1)
    assert session.history[-1]==Event((2,1))
    session.undo(); assert session.history==prior
    session.act('A',1); session.act('B',2)
    assert session.history[-1]==Event((1,2))
    with pytest.raises(IllegalAction): session.act('A',2)

def test_sampling_is_exact_and_injectable(complete):
    rec=complete['A'].get_recommendation((),'B')
    rec=replace(rec,actions=(0,1),probabilities=(F(1,3),F(2,3)))
    class Draw:
        def __init__(self,n): self.n=n
        def randrange(self,n): assert n==3; return self.n
    assert [sample_action(rec,Draw(i)) for i in range(3)]==[0,1,1]
    with pytest.raises(IllegalAction): sample_action(replace(rec,probabilities=()),Random(1))

def test_malformed_and_incompatible_documents(complete):
    s=complete['A']; text=dumps(s)
    for bad in ['not json','[]','{}',text.replace('mean-distinct','wrong-distinct',1)]:
        with pytest.raises(InvalidData): loads(bad)
    document=json.loads(text); document['body']['version']=99
    with pytest.raises(InvalidData): loads(json.dumps(document))
    with pytest.raises(InvalidData): loads(text,s.payoffs.swapped())
    data=unpack(text,'solution')
    data['nodes'][0][1]='-100'
    with pytest.raises(InvalidData): loads(pack('solution',data))
    data=unpack(text,'solution'); data['nodes'].pop()
    with pytest.raises(InvalidData): loads(pack('solution',data))
    data=unpack(text,'solution'); data['nodes'].append(data['nodes'][0])
    with pytest.raises(InvalidData): loads(pack('solution',data))
    with pytest.raises(InvalidData): Session.restore(complete['B'],Session(s).export())

def test_illegal_session_and_history(complete):
    s=complete['A']
    with pytest.raises(IllegalAction): Session(s).act('A',0)
    with pytest.raises(IllegalAction): Session(s).undo()
    with pytest.raises(IllegalAction): s.get_value((Event((99,)),))
    with pytest.raises(IllegalAction): s.get_value(((0,),))

def test_private_snapshot_rejects_wrong_public_history(complete):
    s=complete['A']; session=Session(s,(Event((8,)),Event((7,))))
    session.act('A',0)
    private=session.export_private('A'); public=session.export()
    with pytest.raises(InvalidData): Session.restore(s,public,[private,private])
    session.act('B',0)
    with pytest.raises(InvalidData): Session.restore(s,session.export(),[private])

def test_loading_never_recomputes_equilibrium(complete,monkeypatch):
    import wtc_solver.matrix_game as matrix
    import wtc_solver.solver as solver
    def forbidden(*args,**kwargs):
        raise AssertionError('Loading called the equilibrium optimizer')
    monkeypatch.setattr(matrix,'solve_matrix',forbidden)
    monkeypatch.setattr(solver,'solve_matrix',forbidden)
    monkeypatch.setattr(solver,'solve',forbidden)
    s=complete['A']
    restored=loads(dumps(s))
    assert restored.get_recommendation((Event((0,)),),'A')==s.get_recommendation((Event((0,)),),'A')
