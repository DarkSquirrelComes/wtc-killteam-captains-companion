"""UTF-8 named/legacy CSV and JSON adapters. No UI dependencies."""
import csv
from decimal import Decimal
import io
import json
from wtc_solver import InvalidData, Payoffs
from wtc_solver.payoff import rational
from .config import Configuration, Names

LEGACY = ['player_a', 'player_b', 'table'] + [f'M{i}' for i in range(9)]
PREFIX = ['player_a', 'player_a_name', 'player_b', 'player_b_name', 'table', 'table_name']

def csv_number(value):
    """Prefer exact finite decimals, avoiding Excel's date parsing of e.g. 1/2."""
    d = value.denominator
    two = five = 0
    while d % 2 == 0: d //= 2; two += 1
    while d % 5 == 0: d //= 5; five += 1
    if d != 1: return str(value)
    places = max(two, five)
    if not places: return str(value.numerator)
    digits = str(value.numerator * 2**(places-two) * 5**(places-five)).rjust(places+1, '0')
    return digits[:-places] + '.' + digits[-places:]

def export_csv(config: Configuration | None = None) -> str:
    """27 rows, 243 GP cells. Mission headers are M0|Human readable name."""
    names = config.names if config else Names.defaults()
    output = io.StringIO(newline='')
    writer = csv.writer(output)
    writer.writerow(PREFIX + [f'M{i}|{n}' for i,n in enumerate(names.missions)])
    for a in range(3):
        for b in range(3):
            for t in range(3):
                values = list(map(csv_number, config.payoffs.data[a][b][t])) if config else ['']*9
                writer.writerow([a, names.players_a[a], b, names.players_b[b], t, names.tables[t], *values])
    return output.getvalue()

def export_json(config: Configuration) -> str:
    return json.dumps(config.to_data(), ensure_ascii=False, indent=2)

def import_data(content: str | bytes, filename: str) -> Configuration:
    try:
        text = content.decode('utf-8-sig') if isinstance(content, bytes) else content.lstrip('\ufeff')
        if filename.lower().endswith('.json'):
            data = json.loads(text, parse_float=Decimal)
            return Configuration(Payoffs(data), Names.defaults()) if isinstance(data, list) else Configuration.from_data(data)
        if not filename.lower().endswith('.csv'):
            raise InvalidData('Выберите CSV или JSON. Excel можно сохранить как CSV UTF-8.')
        return import_csv(text)
    except (UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        raise InvalidData('Не удалось прочитать файл: нужен UTF-8 и корректный CSV/JSON.') from exc

def import_csv(text: str) -> Configuration:
    # Excel commonly uses semicolons with decimal commas; accept both explicitly.
    first = text.splitlines()[0] if text.splitlines() else ''
    delimiter = ';' if first.startswith('player_a;') else ','
    reader = csv.reader(io.StringIO(text), delimiter=delimiter, strict=True)
    header = next(reader, [])
    legacy = header == LEGACY
    if not legacy:
        if len(header) != 15 or header[:6] != PREFIX:
            raise InvalidData('Неверный заголовок CSV. Скачайте шаблон приложения (или используйте старый формат).')
        mission_names = []
        for i, h in enumerate(header[6:]):
            ident, separator, name = h.partition('|')
            if ident != f'M{i}' or not separator:
                raise InvalidData('Миссии должны иметь уникальные ID M0…M8 в порядке шаблона.')
            mission_names.append(name)
    labels = [{}, {}, {}]
    tensor = [[[[None]*9 for _ in range(3)] for _ in range(3)] for _ in range(3)]
    seen = set()
    for line, row in enumerate(reader, 2):
        if not row:
            continue
        if len(row) != len(header):
            raise InvalidData(f'Строка {line}: ожидалось {len(header)} столбцов, получено {len(row)}.')
        try:
            indices = (0,1,2) if legacy else (0,2,4)
            ids = tuple(int(row[i]) for i in indices)
        except ValueError as exc:
            raise InvalidData(f'Строка {line}: ID игроков и стола должны быть целыми 0, 1 или 2.') from exc
        if any(i not in range(3) for i in ids):
            raise InvalidData(f'Строка {line}: ID вне диапазона 0…2.')
        if ids in seen:
            raise InvalidData(f'Строка {line}: повтор сочетания игрок A / игрок B / стол {ids}.')
        seen.add(ids)
        if not legacy:
            for group, ident, index in zip(labels, ids, (1,3,5)):
                name = row[index]
                if ident in group and group[ident] != name:
                    raise InvalidData(f'Строка {line}: одному ID соответствуют разные названия.')
                group[ident] = name
        values = []
        for m, cell in enumerate(row[3:] if legacy else row[6:]):
            if not cell.strip():
                raise InvalidData(f'Строка {line}, миссия M{m}: отсутствует оценка GP.')
            try:
                value = rational(cell.replace(',', '.') if delimiter == ';' else cell)
                if not 0 <= value <= 20:
                    raise InvalidData('GP вне диапазона 0…20.')
                values.append(value)
            except InvalidData as exc:
                raise InvalidData(f'Строка {line}, миссия M{m}: нужна числовая оценка от 0 до 20.') from exc
        a,b,t = ids
        tensor[a][b][t] = values
    if len(seen) != 27:
        raise InvalidData(f'Неполная таблица: найдено {len(seen)} из 27 сочетаний игроков и столов.')
    names = Names.defaults() if legacy else Names(*(tuple(g[i] for i in range(3)) for g in labels), tuple(mission_names))
    return Configuration(Payoffs(tensor), names)
