"""Isolation across independent browser sessions and concurrent controllers."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest
from wtc_assistant.controller import CaptainController
from wtc_assistant.import_export import SessionAutosave, export_session, import_session
from wtc_solver import InvalidData

ENTRY = str(Path(__file__).resolve().parents[2] / 'streamlit_app.py')


def test_concurrent_private_saves_even_with_same_imported_session_id(bundle):
    original = CaptainController.start(bundle, 'B')
    encoded = export_session(bundle, original.session)
    stores = [SessionAutosave(), SessionAutosave()]
    controllers = [import_session(encoded, store.save) for store in stores]
    assert controllers[0].session.session_id == controllers[1].session.session_id

    def advance(i):
        c = controllers[i]
        c.confirm_own(i, c.context)
        return c.view()

    with ThreadPoolExecutor(max_workers=2) as pool:
        views = list(pool.map(advance, range(2)))
    assert views[0] != views[1]
    for i, store in enumerate(stores):
        assert store.restore().view() == views[i]
    controllers[0].undo(controllers[0].context)
    assert stores[1].restore().view() == views[1]
    with pytest.raises(InvalidData):
        SessionAutosave().restore()


def test_browser_sessions_do_not_share_names_actions_rng_or_restore(bundle, tmp_path, monkeypatch):
    monkeypatch.delenv('WTC_STORAGE_MODE', raising=False)
    # A leftover local file/path must never become visible in default cloud mode.
    path = tmp_path / 'private-local.json'
    path.write_text('private local data')
    monkeypatch.setenv('WTC_AUTOSAVE_PATH', str(path))
    apps = [AppTest.from_file(ENTRY, default_timeout=60) for _ in range(2)]
    for i, app in enumerate(apps):
        named = bundle.renamed(replace(bundle.config.names, players_a=(f'Captain {i}', 'Second', 'Third')))
        app.session_state['bundle'] = named
        app.session_state['config'] = named.config
        app.run()
        assert not app.exception
        assert not any(b.key == 'restore_autosave' for b in app.button)
        app.radio(key='role').set_value('Защитник').run()
        app.button(key='start').click().run()
        assert not app.exception
    a, b = apps
    assert a.session_state['autosave_store'] is not b.session_state['autosave_store']
    assert a.session_state['rng'] is not b.session_state['rng']
    before = b.session_state['controller'].view()
    c = a.session_state['controller']
    a.selectbox(key=f'choice_{c.context}').set_value(0).run()
    a.button(key='confirm').click().run()
    b.run()
    assert not a.exception and not b.exception
    assert b.session_state['controller'].view() == before
    assert b.session_state['config'].names.players_a[0] == 'Captain 1'
    for app in apps:
        assert app.button(key='restore_autosave').disabled
        app.checkbox(key='replace_session').check().run()
        app.button(key='restore_autosave').click().run()
        assert not app.exception
    assert len(a.session_state['controller'].session.history) == 1
    assert len(b.session_state['controller'].session.history) == 0
    assert path.read_text() == 'private local data'
    fresh = AppTest.from_file(ENTRY, default_timeout=60).run()
    assert not fresh.exception
    assert not fresh.session_state['autosave_store'].available
    assert not any(b.key == 'restore_autosave' for b in fresh.button)


def test_explicit_local_mode_retains_file_restore(tmp_path, monkeypatch):
    from wtc_assistant.import_export import Autosave
    monkeypatch.setenv('WTC_STORAGE_MODE', 'local')
    path = tmp_path / 'local.json'
    monkeypatch.setenv('WTC_AUTOSAVE_PATH', str(path))
    app = AppTest.from_file(ENTRY, default_timeout=60).run()
    assert not app.exception
    assert isinstance(app.session_state['autosave_store'], Autosave)
    assert app.session_state['autosave_store'].path == path
