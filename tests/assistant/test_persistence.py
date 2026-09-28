from dataclasses import replace
import json
import pytest
from wtc_solver import InvalidData
from wtc_solver.serialization import pack,unpack
from wtc_assistant.controller import CaptainController,StaleDecision
from wtc_assistant.import_export import Autosave,export_bundle,import_bundle,export_session,import_session

def step(c):
    v=c.view()
    if v.mode=='own': c.confirm_own(v.options[-1].id,v.context)
    else: c.record_opponent(v.options[-1].id,v.context)

@pytest.mark.parametrize('role',['A','B'])
def test_partial_pending_and_complete_restore_without_solver(bundle,role,monkeypatch):
    import wtc_assistant.solutions as api
    import wtc_solver.solver as solver
    def forbidden(*a,**k): raise AssertionError('Unexpected equilibrium solve')
    monkeypatch.setattr(api,'solve',forbidden); monkeypatch.setattr(solver,'solve',forbidden)
    first=CaptainController.start(bundle,role)
    while len(first.session.history)<3 or first.session.own_commitment is None: step(first)
    encoded=export_session(first.bundle,first.session)
    restored=import_session(encoded)
    assert restored.view()==first.view()
    while first.view().mode!='complete':
        assert first.view()==restored.view()
        step(first); step(restored)
    assert import_session(export_session(first.bundle,first.session)).view()==first.view()

def test_named_policy_compatibility(bundle):
    text=export_bundle(bundle)
    loaded=import_bundle(text,bundle.config)
    assert loaded.pre_roll_a==bundle.pre_roll_a
    assert loaded.attacker_a.nodes==bundle.attacker_a.nodes
    changed=replace(bundle.config,names=replace(bundle.config.names,players_a=('X','Y','Z')))
    with pytest.raises(InvalidData,match='Имена'): import_bundle(text,changed)
    data=unpack(text,'assistant-bundle'); data['compatibility']['package']='999'
    with pytest.raises(InvalidData,match='версия'): import_bundle(pack('assistant-bundle',data))
    changed=replace(bundle.config,payoffs=bundle.config.payoffs.swapped())
    with pytest.raises(InvalidData,match='другой'): import_bundle(text,changed)

def test_corruption_illegal_history_and_version(bundle):
    c=CaptainController.start(bundle,'A')
    text=export_session(bundle,c.session)
    for bad in ('[]','garbage',text.replace('captain-session','unknown',1)):
        with pytest.raises(InvalidData): import_session(bad)
    data=unpack(text,'captain-session'); data['session']['history']=[[99]]
    with pytest.raises(InvalidData): import_session(pack('captain-session',data))
    data=unpack(text,'captain-session'); data['session']['own_commitment']=0
    with pytest.raises(InvalidData): import_session(pack('captain-session',data))

def test_autosave_transactions_and_stale_tab(bundle,tmp_path,monkeypatch):
    path=tmp_path/'save.json'; store=Autosave(path)
    c=CaptainController.start(bundle,'A',store.save)
    stale_store=Autosave(path)
    stale=CaptainController(bundle,c.session,stale_store.save)
    step(c)
    assert store.restore().view()==c.view()
    with pytest.raises(StaleDecision): step(stale)
    before=c.session; original=path.read_bytes()
    import wtc_assistant.import_export as module
    def broken(*a,**k): raise OSError('Disk unavailable')
    monkeypatch.setattr(module.os,'replace',broken)
    with pytest.raises(OSError): step(c)
    assert c.session==before and path.read_bytes()==original
    assert not list(tmp_path.glob('.autosave-*.tmp'))
