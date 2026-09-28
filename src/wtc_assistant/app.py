"""Streamlit rendering only. Game transitions and policy values belong to the controller."""
import os
from importlib.metadata import version
from pathlib import Path
from random import Random
import streamlit as st
from wtc_solver.payoff import benchmark_payoffs
from .config import Configuration, Names
from .controller import CaptainController
from .data import export_csv, export_json, import_data
from .import_export import Autosave, SessionAutosave, export_bundle, export_session, import_bundle, import_legacy_policies, import_session
from .solutions import calculate

def gp(value): return f'{float(value):.2f}'

def rerender():
    st.session_state.pop('sampled', None)
    st.rerun()

def store():
    if 'autosave_store' not in st.session_state:
        mode = os.environ.get('WTC_STORAGE_MODE', 'session')
        if mode == 'local':
            path = os.environ.get('WTC_AUTOSAVE_PATH', 'outputs/assistant/autosave.json')
            st.session_state.autosave_store = Autosave(path)
        elif mode == 'session':
            st.session_state.autosave_store = SessionAutosave()
        else:
            raise ValueError('WTC_STORAGE_MODE должен быть session или local.')
    return st.session_state.autosave_store

def install(controller):
    store().save(controller.bundle, controller.session)
    st.session_state.controller = controller
    st.session_state.bundle = controller.bundle
    st.session_state.config = controller.bundle.config
    rerender()

def sidebar():
    with st.sidebar:
        st.title('WTC · Captain')
        st.caption('3 × 3 · помощник капитана')
        if isinstance(store(), SessionAutosave):
            st.caption('Данные изолированы в этой вкладке. Перед закрытием или обновлением страницы скачайте сессию JSON: после разрыва соединения или перезапуска сервера она может быть потеряна.')
        active = st.session_state.get('controller')
        if active:
            view = active.view()
            st.subheader(f'Мы — {view.our_role.lower()}')
            st.caption('Точная рациональная стратегия · автосохранение включено')
            st.download_button('Скачать сессию JSON', export_session(active.bundle, active.session),
                               'wtc-session.json', 'application/json', key='download_session')
            if st.button('Отменить последнее решение', key='undo',
                         disabled=not active.session.history and active.session.own_commitment is None):
                active.undo(view.context)
                rerender()
        with st.expander('Восстановить сессию', expanded=not bool(active)):
            uploaded = st.file_uploader('Файл сессии JSON', type=['json'], key='session_upload')
            allowed = not active or st.checkbox('Заменить текущую сессию', key='replace_session')
            if st.button('Импортировать сессию', disabled=uploaded is None or not allowed, key='import_session'):
                with st.spinner('Проверяем сохранённые политики, без пересчёта…'):
                    controller = import_session(uploaded.getvalue().decode('utf-8-sig'), store().save)
                install(controller)
            if store().available:
                if st.button('Восстановить автосохранение', disabled=not allowed, key='restore_autosave'):
                    with st.spinner('Восстанавливаем историю и проверяем политики…'):
                        controller = store().restore()
                    st.session_state.controller = controller
                    st.session_state.bundle = controller.bundle
                    st.session_state.config = controller.bundle.config
                    rerender()
        if active:
            with st.expander('Начать другой паринг'):
                confirmed = st.checkbox('Текущую сессию можно закрыть', key='allow_new')
                if st.button('Новая конфигурация', disabled=not confirmed, key='new_configuration'):
                    for key in ('controller', 'bundle', 'config', 'sampled'):
                        st.session_state.pop(key, None)
                    rerender()
        st.caption('Наши GP всегда относятся к нашей команде, независимо от роли.')

def edit_names(config, active=None):
    context = active.context if active else str(hash(config.names))
    with st.expander('Имена игроков, столов и миссий'):
        st.caption('Имена уже загружаются из таблицы. Здесь можно исправить подписи существующих ID без пересчёта.')
        with st.form(f'names_{context}'):
            a,b,t = st.columns(3)
            av = tuple(a.text_input(f'Наш игрок {i+1}', n, key=f'{context}_a{i}') for i,n in enumerate(config.names.players_a))
            bv = tuple(b.text_input(f'Соперник {i+1}', n, key=f'{context}_b{i}') for i,n in enumerate(config.names.players_b))
            tv = tuple(t.text_input(f'Стол {i+1}', n, key=f'{context}_t{i}') for i,n in enumerate(config.names.tables))
            columns = st.columns(3)
            mv = tuple(columns[i%3].text_input(f'Миссия {i+1}', n, key=f'{context}_m{i}') for i,n in enumerate(config.names.missions))
            if st.form_submit_button('Сохранить названия'):
                names = Names(av,bv,tv,mv)
                if active:
                    active.rename(names, active.context)
                    st.session_state.bundle = active.bundle
                    st.session_state.config = active.bundle.config
                else:
                    st.session_state.config = Configuration(config.payoffs, names)
                    if st.session_state.get('bundle'):
                        st.session_state.bundle = st.session_state.bundle.renamed(names)
                rerender()

def setup():
    st.title('Помощник капитана')
    st.write('Загрузите оценки, рассчитайте обе роли и пройдите паринг с рекомендациями на каждом шаге.')
    with st.container(border=True):
        st.subheader('1 · Таблица ожидаемых GP')
        left, right = st.columns([3,2])
        with left:
            uploaded = st.file_uploader('CSV или JSON с оценками', type=['csv','json'], key='payoff_upload')
            if st.button('Загрузить таблицу', disabled=uploaded is None, key='load_input'):
                st.session_state.config = import_data(uploaded.getvalue(), uploaded.name)
                st.session_state.pop('bundle', None)
                rerender()
        with right:
            st.download_button('Скачать CSV-шаблон с именами', '\ufeff'+export_csv(), 'wtc-gp-template.csv', 'text/csv', key='template')
            st.caption('27 строк · 243 оценки от 0 до 20. Имена находятся в том же файле.')
            if st.button('Открыть демонстрационные данные', key='demo'):
                st.session_state.config = Configuration(benchmark_payoffs(), Names.defaults())
                st.session_state.pop('bundle', None)
                rerender()
    config = st.session_state.get('config')
    if config:
        st.success('Таблица проверена: все 243 оценки заполнены.')
        edit_names(config)
        with st.expander('Просмотр и экспорт исходных оценок'):
            st.dataframe([dict(Мы=config.names.players_a[a], Соперник=config.names.players_b[b],
                               Стол=config.names.tables[t], **{f'GP · {n}': str(config.payoffs.data[a][b][t][m]) for m,n in enumerate(config.names.missions)})
                          for a in range(3) for b in range(3) for t in range(3)], hide_index=True)
            st.download_button('Скачать заполненный CSV', '\ufeff'+export_csv(config), 'wtc-gp.csv', 'text/csv')
            st.download_button('Скачать исходные данные JSON', export_json(config), 'wtc-input.json', 'application/json')
    with st.container(border=True):
        st.subheader('2 · Рассчитать или загрузить стратегии')
        bundle = st.session_state.get('bundle')
        if st.button('Рассчитать обе роли', disabled=config is None or bundle is not None, key='calculate', type='primary'):
            progress = st.progress(0, text='Подготовка…')
            st.session_state.bundle = calculate(config, lambda text, n: progress.progress(n/2, text=text))
            rerender()
        policy_file = st.file_uploader('Готовый комплект политик', type=['json'], key='policy_upload')
        if st.button('Загрузить политики без пересчёта', disabled=policy_file is None, key='load_bundle'):
            with st.spinner('Проверяем совместимость и равновесные условия…'):
                bundle = import_bundle(policy_file.getvalue().decode('utf-8-sig'), config)
            st.session_state.bundle, st.session_state.config = bundle, bundle.config
            rerender()
        with st.expander('Загрузить два файла старого решателя'):
            st.caption('В старых файлах нет имён. После проверки GP привяжем их к загруженной таблице.')
            a = st.file_uploader('attacker_A.json', type=['json'], key='legacy_a')
            b = st.file_uploader('attacker_B.json', type=['json'], key='legacy_b')
            attach = st.checkbox('Подтверждаю соответствие ID и имён таблицы', key='legacy_attach')
            if st.button('Привязать старые политики', disabled=not(config and a and b and attach), key='load_legacy'):
                with st.spinner('Проверяем обе политики…'):
                    st.session_state.bundle = import_legacy_policies(config, a.getvalue().decode('utf-8-sig'), b.getvalue().decode('utf-8-sig'))
                rerender()
    bundle = st.session_state.get('bundle')
    if bundle:
        a,b,c = st.columns(3)
        a.metric('Мы атакуем · ожидаемые GP', gp(bundle.attacker_a.get_value().team_a))
        b.metric('Мы защищаемся · ожидаемые GP', gp(bundle.attacker_b.get_value().team_a))
        c.metric('До roll-off · 50 / 50', gp(bundle.pre_roll_a))
        a.caption(f'Соперник: {gp(bundle.attacker_a.get_value().team_b)} GP')
        b.caption(f'Соперник: {gp(bundle.attacker_b.get_value().team_b)} GP')
        c.caption(f'Соперник: {gp(60-bundle.pre_roll_a)} GP')
        st.caption(f'Точные рациональные вычисления. Расчёт A: {bundle.attacker_a.statistics["solve_seconds"]:.2f} с; '
                   f'B: {bundle.attacker_b.statistics["solve_seconds"]:.2f} с. Выбрано одно равновесие с максимальной поддержкой.')
        st.download_button('Скачать обе политики', export_bundle(bundle), 'wtc-policies.json', 'application/json')
        role = st.radio('3 · Наша роль после roll-off', ['Атакующий', 'Защитник'], horizontal=True, key='role')
        if st.button('Начать паринг', key='start', type='primary'):
            controller = CaptainController.start(bundle, 'A' if role == 'Атакующий' else 'B', store().save)
            st.session_state.controller = controller
            rerender()

def play(controller):
    view = controller.view()
    st.caption(f'МЫ — {view.our_role.upper()} · ПОДТВЕРЖДЕНО ЭТАПОВ: {len(view.history)} / 9')
    st.title(view.title)
    left, right = st.columns([3,2], gap='large')
    with right:
        a,b = st.columns(2)
        a.metric('Наши ожидаемые GP', gp(view.value.team_a))
        b.metric('GP соперника', gp(view.value.team_b))
        st.caption('Оценка с учётом нашего зафиксированного выбора, против равновесной смеси соперника; не гарантия.'
                   if view.mode == 'reveal' else
                   'Условная оценка итогового счёта при текущей публичной истории и оптимальной дальнейшей игре.')
        if view.shields: st.write(f'Щиты: {view.shields[0]} · {view.shields[1]}')
        st.subheader('Текущие пары')
        if view.pairs:
            st.dataframe([{'Мы': p.ours, 'Соперник': p.opponent, 'Стол': p.table or '—', 'Миссия': p.mission or '—',
                           'GP мы': gp(p.gp_a) if p.gp_a is not None else '—',
                           'GP они': gp(p.gp_b) if p.gp_b is not None else '—'} for p in view.pairs], hide_index=True)
        else: st.caption('Пары появятся после раскрытия выборов мечей.')
        with st.expander('Миссии и столы', expanded=True):
            st.dataframe([{'Миссия': r.name, 'Статус': r.status} for r in view.missions], hide_index=True, height=350)
            st.caption(' · '.join(f'{r.name}: {r.status.lower()}' for r in view.tables))
    with left:
        if view.mode == 'complete':
            st.success('Все три матча назначены. Ожидаемые GP команд суммируются в 60.')
            st.write(f'**{gp(view.value.team_a)} : {gp(view.value.team_b)}**')
        else:
            heading = 'Наш ход' if view.mode == 'own' else 'Запишите раскрытый выбор соперника'
            st.subheader(heading)
            if view.own_commitment:
                st.info(f'Наш выбор зафиксирован: {view.own_commitment}. Дождитесь раскрытия обоих выборов.')
            if view.mode == 'own':
                st.dataframe([{'Действие': x.name, 'Вероятность': x.percent,
                               'Ожидаемые GP': gp(x.expected_a)} for x in view.options], hide_index=True)
                st.caption(view.explanation)
                if view.simultaneous:
                    st.caption('Оценка отдельного действия — против равновесной смеси соперника, а не гарантированный результат.')
                key = f'choice_{view.context}'
                if st.button('Выбрать случайно по стратегии', key='sample'):
                    proposal = controller.propose_sample(st.session_state.rng)
                    st.session_state.sampled = proposal
                    st.session_state[key] = proposal.action
                proposal = st.session_state.get('sampled')
                if proposal and proposal.context == view.context:
                    name = next(x.name for x in view.options if x.id == proposal.action)
                    st.info(f'Случайно предложено: {name}. Решение ещё не записано; подтвердите или выберите вручную.')
            else:
                key = f'choice_{view.context}'
                st.caption('Запишите фактическое действие соперника. Оно может отличаться от равновесной стратегии.')
            labels = {x.id: x.name for x in view.options}
            selected = st.selectbox('Фактический выбор', list(labels), index=None,
                                    format_func=labels.get, key=key, placeholder='Выберите действие…')
            revealed = view.mode != 'reveal' or st.checkbox('Оба выбора уже раскрыты', key=f'revealed_{view.context}')
            label = 'Подтвердить наш выбор' if view.mode == 'own' else 'Записать выбор соперника'
            if st.button(label, disabled=selected is None or not revealed, type='primary', key='confirm'):
                if view.mode == 'own': controller.confirm_own(selected, view.context)
                else: controller.record_opponent(selected, view.context)
                rerender()
        with st.expander('История · возврат и исправление'):
            for i,line in enumerate(view.history): st.write(f'{i+1}. {line}')
            if view.history:
                keep = st.selectbox('Вернуться к состоянию', list(range(len(view.history)+1)),
                                    format_func=lambda n: 'До первого бана' if n == 0 else f'После этапа {n}', key=f'rewind_{view.context}')
                discard = st.checkbox(f'Удалить последующие решения ({len(view.history)-keep}) и незавершённый выбор', key=f'discard_{view.context}')
                if st.button('Вернуться и исправить', disabled=not discard, key='rewind'):
                    controller.rewind(keep, view.context)
                    rerender()
        edit_names(controller.bundle.config, controller)
        with st.expander('Диагностика'):
            if st.checkbox('Показать внутренние ID и точные дроби', key='diagnostics'):
                st.write({'stage': view.stage.name, 'revision': controller.session.revision,
                          'value_a': str(view.value.team_a), 'value_b': str(view.value.team_b)})
                st.dataframe([{'ID': x.id, 'Название': x.name, 'Вероятность': str(x.probability),
                               'GP': str(x.expected_a), 'Гарантия GP модели': str(x.guarantee_a)} for x in view.options], hide_index=True)

def main():
    st.set_page_config(page_title='WTC · Помощник капитана', page_icon='♟', layout='wide')
    st.markdown('<style>.block-container{padding-top:2rem;max-width:1440px}h1{font-size:2rem!important}</style>', unsafe_allow_html=True)
    if 'rng' not in st.session_state: st.session_state.rng = Random()
    try:
        sidebar()
        if st.session_state.get('controller'): play(st.session_state.controller)
        else: setup()
    except (ValueError, OSError, UnicodeError) as exc:
        st.error(f'Не удалось выполнить действие: {exc}')
        st.caption('При ошибке автосохранения новое решение не фиксируется. Исправьте ввод или восстановите последнее автосохранение.')
    st.divider()
    st.caption(f'WTC Captain · v{version("wtc-solver")} · «Первый щит»')

if __name__ == '__main__': main()
