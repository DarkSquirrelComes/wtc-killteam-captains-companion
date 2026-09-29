"""Streamlit input editor; draft operations and validation live in draft.py."""
from dataclasses import replace
import streamlit as st
from .catalogue import TEAMS
from .config import Names
from .draft import Draft


def commit(candidate):
    current=st.session_state.input_draft
    if candidate != current:
        st.session_state.draft_undo=(st.session_state.get('draft_undo',[])+[current])[-50:]
        st.session_state.input_draft=candidate
        st.session_state.draft_revision=st.session_state.get('draft_revision',0)+1


def cell_changed(key,coords):
    try:
        commit(st.session_state.input_draft.edit([(coords,st.session_state[key])]))
    except ValueError as exc:
        st.session_state.draft_error=str(exc)
        st.session_state.draft_revision=st.session_state.get('draft_revision',0)+1


def line_action(a,b,axis,target,action):
    d=st.session_state.input_draft
    coords=d.region(a,b,axis,target)
    if action == 'copy':
        # Snapshot, not a reference to a row which may subsequently change.
        st.session_state.draft_clipboard=tuple(d.get(*c) for c in coords)
        return
    try:
        if action == 'paste':
            values=st.session_state.get('draft_clipboard',())
            if len(values)!=len(coords): raise ValueError('Размер скопированной строки или столбца не совпадает.')
            commit(d.edit(zip(coords,values)))
        else:
            commit(d.bulk(a,b,axis,target,'fill' if action=='ten' else 'shift',
                          10 if action=='ten' else 1 if action=='plus' else -1))
    except ValueError as exc:
        st.session_state.draft_error=str(exc)


def line_buttons(a,b,axis,target,label):
    copied=st.session_state.get('draft_clipboard',())
    size=3 if axis=='mission' else 9
    buttons=st.columns(5,gap=None,wrap=False)
    for col,action,text,help_text in zip(buttons,
            ('plus','minus','copy','paste','ten'),('+','−','⧉','↧','10'),
            ('Увеличить на 1','Уменьшить на 1','Копировать','Вставить','Заполнить десятками')):
        col.button(text,key=f'line_{axis}_{target}_{action}',help=f'{label}: {help_text}',
                   disabled=action=='paste' and len(copied)!=size,
                   on_click=line_action,args=(a,b,axis,target,action),width='stretch')


def render():
    st.title('Заполнить оценки на сайте')
    st.caption('Все оценки — ожидаемые GP нашей команды. Пустая ячейка означает, что оценка ещё не введена. Подтверждайте ввод Enter или переходом в другую ячейку.')
    d=st.session_state.input_draft
    revision=st.session_state.get('draft_revision',0)
    if st.session_state.get('draft_error'):
        st.error(st.session_state.pop('draft_error'))
    if st.button('Вернуться к расчёту',key='editor_back'):
        st.session_state.editor_open=False
        st.rerun()
    with st.expander('Составы, карты и миссии',expanded=d.filled==0):
        with st.form(f'draft_names_{revision}'):
            left,right=st.columns(2)
            groups=[]
            for group,column,title in ((d.names.players_a,left,'Наш игрок'),(d.names.players_b,right,'Соперник')):
                selected=[]
                for i,name in enumerate(group):
                    options=list(dict.fromkeys([name,*TEAMS]))
                    selected.append(column.selectbox(f'{title} {i+1}',options,index=0,
                                    accept_new_options=True,key=f'draft_name_{title}_{i}_{revision}'))
                groups.append(tuple(selected))
            st.caption('Выберите команду Kill Team или впишите своё имя. Для одинаковых команд добавьте ник, например «Legionaries — Алексей». Список — подсказки, не ограничение допуска команд.')
            cols=st.columns(3)
            tables=tuple(cols[i].text_input(f'Карта {i+1}',d.names.tables[i]) for i in range(3))
            missions=tuple(cols[i%3].text_input(f'Миссия {i+1}',d.names.missions[i]) for i in range(9))
            if st.form_submit_button('Применить названия'):
                commit(replace(d,names=Names(*groups,tables,missions)))
                st.rerun()
    st.subheader('Выберите матчап')
    pair=st.session_state.get('draft_pair',0)
    for a in range(3):
        cols=st.columns(3)
        for b in range(3):
            count=sum(d.get(a,b,t,m) is not None for t in range(3) for m in range(9))
            if cols[b].button(f'{d.names.players_a[a]} × {d.names.players_b[b]} · {count}/27',
                              key=f'matchup_{a}_{b}',type='primary' if pair==a*3+b else 'secondary',width='stretch'):
                st.session_state.draft_pair=a*3+b
                st.rerun()
    a,b=divmod(pair,3)
    st.subheader(f'{d.names.players_a[a]} × {d.names.players_b[b]}')
    transpose=st.toggle('Карты по строкам',key='draft_transpose')
    columns=d.names.missions if transpose else d.names.tables
    rows=d.names.tables if transpose else d.names.missions
    st.caption('Для строки или столбца: + / − — изменить на 1; ⧉ — копировать; ↧ — вставить; 10 — заполнить десятками. Пустые ячейки кнопки ± не меняют.')
    # Fixed column geometry keeps every toolbar aligned with its cells, including
    # the transposed view. Narrow screens scroll horizontally inside the grid.
    st.markdown('<style>.st-key-input_grid{overflow-x:auto}.st-key-input_grid [data-testid="stColumn"]{min-width:0!important}.st-key-input_grid button{min-width:0!important;padding:0 2px!important}.st-key-input_grid button p{font-size:13px}</style>',unsafe_allow_html=True)
    with st.container(key='input_grid'):
        with st.container(width=max(780, len(columns)*150+320)):
            widths=[1.2]+[1.5]*len(columns)+[2.2]
            header=st.columns(widths,gap='small',wrap=False)
            for c,name in enumerate(columns):
                with header[c+1]:
                    st.write(name)
                    line_buttons(a,b,'mission' if transpose else 'table',c,name)
            for r,name in enumerate(rows):
                row=st.columns(widths,gap='small',wrap=False,vertical_alignment='center')
                row[0].write(name)
                for c in range(len(columns)):
                    t,m=(r,c) if transpose else (c,r)
                    v=d.get(a,b,t,m)
                    key=f'gp_cell_{revision}_{pair}_{t}_{m}'
                    row[c+1].text_input(f'{name} / {columns[c]}',value='' if v is None else str(v),
                        key=key,label_visibility='collapsed',on_change=cell_changed,args=(key,(a,b,t,m)))
                with row[-1]:
                    line_buttons(a,b,'table' if transpose else 'mission',r,name)
    st.caption('Подтвердите ввод Enter или переходом в другую ячейку. Копирование строки/столбца сохраняет снимок, который можно вставить и в другой матчап. Вставка доступна при совпадении размера.')
    if st.button('Отменить последнее изменение',disabled=not st.session_state.get('draft_undo'),key='draft_undo_button',shortcut='Ctrl+Z'):
        st.session_state.input_draft=st.session_state.draft_undo.pop()
        st.session_state.draft_revision=revision+1
        st.rerun()
    st.progress(d.filled/243,text=f'Заполнено {d.filled} из 243')
    st.download_button('Скачать черновик JSON',d.dumps(),'wtc-draft.json','application/json',key='draft_download')
    with st.expander('Восстановить черновик'):
        uploaded=st.file_uploader('Черновик JSON',type=['json'],key='draft_upload')
        confirmed=st.checkbox('Заменить текущий черновик',key='draft_replace')
        if st.button('Загрузить черновик',disabled=uploaded is None or not confirmed,key='draft_restore'):
            commit(Draft.loads(uploaded.getvalue().decode('utf-8-sig')))
            st.rerun()
    st.caption('Черновик доступен только в этой сессии. Скачайте его перед обновлением или закрытием страницы. В расчёт попадают только оценки после нажатия кнопки ниже.')
    if st.button('Использовать эти оценки',disabled=d.filled!=243,type='primary',key='draft_apply'):
        config=d.configuration()
        if config != st.session_state.get('config'):
            st.session_state.pop('bundle',None)
        st.session_state.config=config
        st.session_state.editor_open=False
        st.rerun()
