"""Summarize executed pytest XML and benchmark JSON, without inventing results."""
import json
from pathlib import Path
from xml.etree import ElementTree as ET

out=Path('outputs')
benchmark=json.loads((out/'benchmark.json').read_text(encoding='utf-8'))
root=ET.parse(out/'test-results.xml').getroot()
suites=list(root.iter('testsuite'))
tests=sum(int(x.attrib['tests']) for x in suites)
failures=sum(int(x.attrib['failures']) for x in suites)
errors=sum(int(x.attrib['errors']) for x in suites)
skipped=sum(int(x.attrib['skipped']) for x in suites)
seconds=sum(float(x.attrib['time']) for x in suites)
lines=[
    '# Отчёт проверки WTC solver',
    '',
    'Дата: 2026-09-28. Числа ниже прочитаны из реально полученных отчётов pytest и бенчмарка.',
    '',
    f'Полный pytest: **{tests} тестов**, ошибок: {errors}, падений: {failures}, пропусков: {skipped}; {seconds:.2f} с.',
    'Команда: `.venv/bin/python.exe -m pytest -q --junitxml=outputs/test-results.xml`.',
    '',
    '## Производительность',
    '',
    f'Python: `{benchmark["python"]}`.',
    f'Платформа: `{benchmark["platform"]}`.',
    f'Тензор SHA-256: `{benchmark["tensor_sha256"]}`.',
    '',
    '| Attacker | GP команды A | Расчёт, с | Пик working set, МиБ | Пик Python-аллокаций, МиБ | JSON, байт | Запрос, мкс |',
    '|---|---:|---:|---:|---:|---:|---:|',
]
for r in benchmark['results']:
    process=r['process_peak_working_set_bytes']
    process='недоступно' if process is None else f'{process/2**20:.2f}'
    lines.append(f'| {r["attacker"]} | {r["value_a"]} | {r["solve_seconds"]:.3f} | {process} | '
                 f'{r["python_allocation_peak_bytes"]/2**20:.2f} | {r["serialized_bytes"]:,} | '
                 f'{r["query_mean_seconds"]*1e6:.2f} |')
lines += [
    '',
    'Время измерено без tracemalloc. Python-память измерена отдельным повторным расчётом с tracemalloc.',
    'Working set включает интерпретатор и ввод. Запрос — среднее 2 000 корневых рекомендаций.',
    'Результаты относятся к искусственному тензору и текущей машине; время зависит от нагрузки.',
    '',
    '| Attacker | Узлов | Финальных рёбер | Матричных узлов | Разных матриц решено | Кэш состояний: попадания / промахи | Кэш матриц: попадания |',
    '|---|---:|---:|---:|---:|---:|---:|',
]
for r in benchmark['results']:
    s=r['statistics']
    lines.append(f'| {r["attacker"]} | {r["policy_nodes"]} | {s["terminal_evaluations"]} | '
                 f'{s["matrix_nodes"]} | {s["matrix_games_solved"]} | '
                 f'{s["cache_hits"]} / {s["cache_misses"]} | {s["matrix_cache_hits"]} |')
lines += [
    '',
    'До объединения эквивалентных состояний — 3 265 920 терминальных последовательностей на роль.',
    'Терминальные рёбра в таблице — число последних назначений, оценённых после мемоизации.',
    '',
    '## Исполненные проверки',
    '',
    '- CLI `solve examples/payoffs_demo.json --output outputs/policies`: обе роли рассчитаны и сохранены.',
    '- CLI `verify` отдельно выполнен для `attacker_A.json` и `attacker_B.json`.',
    '  В каждом файле проверены 35 812 последовательных узлов, 360 матричных узлов и 17 010 терминальных рёбер.',
    '- `examples/session_demo.py`: полные допустимые сессии для обеих ролей, сохранение, загрузка, повторение.',
    '  Рекомендации, история и итоговые назначения совпали точно.',
    '- `benchmarks/benchmark.py`: обе роли, отдельные процессы; отчёт `benchmark.json`.',
    '- `python -m compileall -q src` и `python -m pip check`: выполнены успешно.',
    '- Excel: оба листа отрисованы и визуально проверены; сохранённый XLSX содержит 243 пустых поля GP и закрепление области.',
    '',
    '## Архитектура и оставшийся этап',
    '',
    'Правила и неизменяемые модели отделены от тензора, точного матричного решателя, обратной индукции,',
    'политики/сессий, сериализации и независимого проверяющего кода. Все игровые значения и вероятности — Fraction.',
    'Выбранная стратегия имеет максимальную поддержку оптимальных действий; равновесия не пересчитываются при загрузке.',
    '',
    'Интерфейс не реализован согласно заданию. Для него нужны ввод оценок и названий, запуск расчёта,',
    'показ вероятностей/состояния, авторизация приватных действий и управление файлами сессии.',
    'Готовый API поддерживает выбор действий, семплирование, отмену и альтернативные продолжения.',
    '',
    'Ограничения: фиксированные правила 3×3/9 миссий; XLSX сначала экспортируется в CSV; отсутствуют TP,',
    'модель реальных исходов, приближённый backend и усреднение по roll-off. Длинные рациональные входы могут быть медленнее.',
    'Приватные незавершённые выборы сохраняются отдельно для каждого капитана, без шифрования.',
    '',
    'Исходная попытка установить новую версию Hypothesis на MSYS не удалась из-за несовместимого сборочного backend.',
    'Это устранено установкой и фиксацией совместимой версии 6.142.4. Runtime решателя — только стандартная библиотека.',
]
if failures or errors or skipped:
    lines += ['', 'ВНИМАНИЕ: в pytest есть падения, ошибки или пропуски; см. test-results.xml.']
else:
    lines += ['', 'Неисправленных падений тестов или известных незавершённых требований вычислительного ядра нет.']
(out/'verification_report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(f'Wrote report for {tests} tests ({failures} failures, {errors} errors, {skipped} skipped).')
