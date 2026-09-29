from fractions import Fraction as F
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
from wtc_assistant.config import Names
from wtc_assistant.draft import Draft

ENTRY=str(Path(__file__).resolve().parents[2]/'streamlit_app.py')

def test_edit_active_csv_replaces_old_draft_and_applies_changes():
    from wtc_assistant.data import export_csv, import_data
    config=Draft(Names.defaults(),(F(7),)*243).configuration()
    loaded=import_data(export_csv(config),'scores.csv')
    app=AppTest.from_file(ENTRY,default_timeout=45).run()
    assert app.button(key='open_editor').label=='Заполнить на сайте'
    app.session_state['config']=loaded
    app.session_state['input_draft']=Draft(Names.defaults())
    app.run()
    assert app.button(key='open_editor').label=='Редактировать таблицу на сайте'
    app.button(key='open_editor').click().run()
    assert app.session_state['input_draft']==Draft.from_config(loaded)
    app.button(key='line_mission_0_plus').click().run()
    assert app.session_state['config']==loaded  # Only explicit apply updates the active input.
    app.session_state['bundle']='obsolete policy placeholder'
    app.button(key='draft_apply').click().run()
    assert not app.exception
    assert app.session_state['config'].payoffs.data[0][0][0][0]==8
    assert app.session_state['config'].payoffs.data[0][0][0][1]==7
    assert app.session_state['config'].names==loaded.names
    assert 'bundle' not in app.session_state
    assert app.button(key='open_editor').label=='Редактировать таблицу на сайте'

def test_exact_partial_roundtrip_and_validation():
    d=Draft(Names.defaults()).edit([((0,1,2,3),'1/3')])
    assert d.filled==1 and d.get(0,1,2,3)==F(1,3)
    assert Draft.loads(d.dumps())==d
    with pytest.raises(ValueError): d.configuration()
    with pytest.raises(ValueError): d.edit([((0,0,0,0),21)])
    with pytest.raises(ValueError): d.edit([((3,0,0,0),10)])
    with pytest.raises(ValueError): Draft.loads('{}')

def test_bulk_axes_copy_shift_atomic_and_complete():
    d=Draft(Names.defaults()).bulk(0,0,'mission',2,'fill','7.5')
    assert d.filled==3
    assert all(d.get(0,0,t,2)==F(15,2) for t in range(3))
    d=d.bulk(0,0,'mission',3,'copy',source=2)
    d=d.bulk(0,0,'table',1,'shift',1)
    assert d.get(0,0,1,3)==F(17,2) and d.get(0,0,1,0) is None
    d=d.bulk(0,0,'table',2,'copy',source=1)
    assert d.get(0,0,2,3)==F(17,2)
    copied=d.bulk(1,2,'all',0,'copy',source=0)
    assert all(copied.get(1,2,t,m)==d.get(0,0,t,m) for t in range(3) for m in range(9))
    high=d.edit([((0,0,0,0),20)])
    with pytest.raises(ValueError): high.bulk(0,0,'all',0,'shift',1)
    assert high.get(0,0,1,3)==F(17,2)  # No partial mutation.
    for a in range(3):
        for b in range(3): d=d.bulk(a,b,'all',0,'fill',10)
    assert Draft.from_config(d.configuration())==d and d.filled==243
    assert d.bulk(0,0,'all',0,'clear').filled==216

def test_editor_flow_and_session_isolation():
    app=AppTest.from_file(ENTRY,default_timeout=45).run()
    app.button(key='open_editor').click().run()
    assert not app.exception
    assert app.button(key='draft_apply').disabled
    assert not any(x.key=='bulk_area' for x in app.selectbox)
    assert app.button(key='line_mission_0_paste').disabled
    app.button(key='line_mission_0_ten').click().run()
    assert app.session_state['input_draft'].filled==3
    app.button(key='line_mission_0_copy').click().run()
    app.button(key='line_mission_0_plus').click().run()
    assert app.session_state['input_draft'].get(0,0,0,0)==11
    app.button(key='matchup_1_2').click().run()
    app.button(key='line_mission_1_paste').click().run()
    assert app.session_state['input_draft'].get(1,2,0,1)==10  # Snapshot from before +1.
    assert app.session_state['input_draft'].filled==6
    app.button(key='draft_undo_button').click().run()
    assert app.session_state['input_draft'].filled==3
    other=AppTest.from_file(ENTRY,default_timeout=45).run()
    other.button(key='open_editor').click().run()
    assert other.session_state['input_draft'].filled==0
    assert other.button(key='line_mission_0_paste').disabled
    revision=app.session_state['draft_revision']
    app.text_input(key=f'gp_cell_{revision}_5_1_2').set_value('8.5').run()
    assert app.session_state['input_draft'].get(1,2,1,2)==F(17,2)
    app.toggle(key='draft_transpose').set_value(True).run()
    app.button(key='line_table_1_copy').click().run()
    app.button(key='line_table_2_paste').click().run()
    assert app.session_state['input_draft'].get(1,2,2,2)==F(17,2)
    app.button(key='line_table_2_minus').click().run()
    assert app.session_state['input_draft'].get(1,2,2,2)==F(15,2)
    for a in range(3):
        for b in range(3):
            app.button(key=f'matchup_{a}_{b}').click().run()
            for t in range(3): app.button(key=f'line_table_{t}_ten').click().run()
    app.button(key='draft_apply').click().run()
    assert not app.exception
    assert app.session_state['config'].payoffs.data[2][2][2][8]==10
    assert not app.button(key='calculate').disabled
