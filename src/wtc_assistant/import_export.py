"""Self-contained checksummed sessions, policy bundles and atomic autosave."""
from importlib.metadata import version
import json
import os
from pathlib import Path
import tempfile
from threading import Lock
from wtc_solver import Event, InvalidData
from wtc_solver.serialization import POLICY_RULE, VERSION, loads, pack, unpack
from .config import Configuration
from .controller import CaptainController
from .session import CaptainSession
from .solutions import PolicyBundle

_SAVE_LOCKS: dict[Path, Lock] = {}

def compatibility():
    return dict(package=version('wtc-solver'), policy_format=VERSION, selection=POLICY_RULE)

def bundle_data(bundle):
    return dict(compatibility=compatibility(), config=bundle.config.to_data(), policies=list(bundle.documents))

def read_bundle(data, expected: Configuration | None = None):
    try:
        if data['compatibility'] != compatibility():
            raise InvalidData('Несовместимая версия решателя или формата политики.')
        config = Configuration.from_data(data['config'])
        if expected is not None:
            if expected.payoffs != config.payoffs:
                raise InvalidData('Политики рассчитаны для другой таблицы GP.')
            if expected.names != config.names:
                raise InvalidData('Имена или их привязка к ID отличаются. Загрузите исходную конфигурацию; переименовать ID можно отдельно.')
        documents = data['policies']
        if not isinstance(documents, list) or len(documents) != 2:
            raise InvalidData('Нужны обе политики.')
        a,b = [loads(text, config.payoffs) for text in documents]
        if a.attacker_team != 'A' or b.attacker_team != 'B':
            raise InvalidData('Неверный порядок политик по ролям.')
        return PolicyBundle(config, a, b, tuple(documents))
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidData(f'Не удалось загрузить политики: {exc}') from exc

def export_bundle(bundle): return pack('assistant-bundle', bundle_data(bundle))

def import_bundle(text, expected=None): return read_bundle(unpack(text, 'assistant-bundle'), expected)

def import_legacy_policies(config, a_text, b_text):
    """Explicitly attach names to old solver files, which have no name metadata."""
    a,b = loads(a_text, config.payoffs), loads(b_text, config.payoffs)
    return PolicyBundle.create(config, a, b)

def export_session(bundle: PolicyBundle, session: CaptainSession) -> str:
    return pack('captain-session', dict(bundle=bundle_data(bundle), session=dict(
        attacker=session.attacker_team, history=[list(e.actions) for e in session.history],
        own_commitment=session.own_commitment, revision=session.revision, session_id=session.session_id)))

def import_session(text: str, persist=None) -> CaptainController:
    try:
        data = unpack(text, 'captain-session')
        bundle = read_bundle(data['bundle'])
        s = data['session']
        session = CaptainSession(s['attacker'], tuple(Event(tuple(a)) for a in s['history']),
                                 s['own_commitment'], s['revision'], s['session_id'])
        return CaptainController(bundle, session, persist)
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidData(f'Не удалось восстановить сессию: {exc}') from exc

class Autosave:
    """One local captain workspace. Atomic replace; no partial overwrite on error.

    Optimistic file-digest checks reject writes from stale tabs/controllers.
    The UI keeps one Autosave instance per browser session.
    """
    def __init__(self, path):
        self.path = Path(path)
        self._expected = self._digest()

    @property
    def available(self):
        return self.path.exists()

    def _digest(self):
        import hashlib
        return hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.exists() else None

    def save(self, bundle, session):
        # Serialize browser-session writers inside the single Streamlit process.
        lock = _SAVE_LOCKS.setdefault(self.path.resolve(), Lock())
        with lock:
            self._save_locked(bundle, session)

    def _save_locked(self, bundle, session):
        from .controller import StaleDecision
        if self._digest() != self._expected:
            raise StaleDecision('Автосохранение изменено в другой вкладке. Сначала восстановите последнюю сессию.')
        text = export_session(bundle, session)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                             prefix='.autosave-', suffix='.tmp', delete=False) as f:
                temporary = Path(f.name)
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, self.path)
            self._expected = self._digest()
        finally:
            if temporary is not None and temporary.exists(): temporary.unlink()

    def restore(self):
        text = self.path.read_text(encoding='utf-8')
        controller = import_session(text, self.save)
        self._expected = self._digest()
        return controller


class SessionAutosave:
    """Private in-memory snapshot, owned exclusively by one Streamlit session.

    No filesystem path, global registry, or client-supplied session ID is used.
    A disconnected/expired browser session must restore from its exported JSON.
    """
    def __init__(self):
        self._text = None

    @property
    def available(self):
        return self._text is not None

    def save(self, bundle, session):
        self._text = export_session(bundle, session)

    def restore(self):
        if self._text is None:
            raise InvalidData('В этой вкладке нет сохранённой сессии.')
        return import_session(self._text, self.save)
