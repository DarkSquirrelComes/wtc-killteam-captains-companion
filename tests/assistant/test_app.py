"""Real Streamlit script execution with AppTest, no browser required."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ENTRY = str(Path(__file__).resolve().parents[2] / 'streamlit_app.py')

@pytest.fixture
def app(bundle,tmp_path,monkeypatch):
    monkeypatch.setenv('WTC_AUTOSAVE_PATH',str(tmp_path/'autosave.json'))
    at=AppTest.from_file(ENTRY,default_timeout=45)
    at.session_state['bundle']=bundle
    at.session_state['config']=bundle.config
    at.run()
    assert not at.exception
    return at

def test_empty_start_and_template(tmp_path,monkeypatch):
    monkeypatch.setenv('WTC_AUTOSAVE_PATH',str(tmp_path/'empty.json'))
    at=AppTest.from_file(ENTRY,default_timeout=45).run()
    assert not at.exception
    assert at.button(key='calculate').disabled
    assert at.button(key='load_input').disabled
    at.button(key='demo').click().run()
    assert not at.exception
    assert at.session_state['config'].payoffs.data[0][0][0][0]==0
    assert not at.button(key='calculate').disabled

@pytest.mark.parametrize('role',['Атакующий','Защитник'])
def test_full_ui_pairing_and_undo(app,role):
    app.radio(key='role').set_value(role).run()
    app.button(key='start').click().run()
    assert not app.exception
    count=0
    while app.session_state['controller'].view().mode!='complete':
        c=app.session_state['controller']; view=c.view()
        assert app.button(key='confirm').disabled  # No automatically chosen opponent action.
        if view.mode in ('opponent', 'reveal'):
            hints = next(d.value for d in app.dataframe if 'Действие соперника' in d.value.columns)
            assert list(hints['Вероятность']) == [x.percent for x in view.options]
            assert list(hints['В стратегии']) == ['✓' if x.probability > 0 else '—' for x in view.options]
        # AppTest select_index supplies a rendered label; our widget's actual
        # values are stable integer IDs, so set that value explicitly.
        app.selectbox(key=f'choice_{view.context}').set_value(view.options[0].id).run()
        if view.mode=='reveal': app.checkbox(key=f'revealed_{view.context}').check().run()
        app.button(key='confirm').click().run()
        assert not app.exception and not app.error
        count+=1
        assert count<15
    view=app.session_state['controller'].view()
    assert view.value.team_a+view.value.team_b==60
    assert len(view.pairs)==3
    app.button(key='undo').click().run()
    assert app.session_state['controller'].view().mode!='complete'
    assert not app.exception

def test_ui_sample_is_proposal_then_confirm(app):
    app.radio(key='role').set_value('Защитник').run()
    app.button(key='start').click().run()
    c=app.session_state['controller']; original=c.session
    app.button(key='sample').click().run()
    assert not app.exception
    assert c.session==original
    assert any('Решение ещё не записано' in x.value for x in app.info)
    app.button(key='confirm').click().run()
    assert c.session!=original
    assert not app.exception

def test_ui_calculation_only_on_button(bundle,tmp_path,monkeypatch):
    import wtc_assistant.app as module
    calls=[]
    def calculate(config,progress):
        calls.append(config)
        progress('A',0); progress('B',1); progress('Готово',2)
        return bundle
    monkeypatch.setattr(module,'calculate',calculate)
    monkeypatch.setenv('WTC_AUTOSAVE_PATH',str(tmp_path/'state.json'))
    at=AppTest.from_file(ENTRY,default_timeout=45)
    at.session_state['config']=bundle.config
    at.run()
    assert not calls
    at.button(key='calculate').click().run()
    at.run()
    assert len(calls)==1 and at.button(key='calculate').disabled
    assert not at.exception
