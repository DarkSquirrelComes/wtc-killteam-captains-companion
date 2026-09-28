import csv
from dataclasses import replace
import io
import json
import pytest
from wtc_solver import InvalidData
from wtc_assistant.config import Names
from wtc_assistant.data import export_csv, export_json, import_data

def rewrite(text, callback, delimiter=','):
    rows = list(csv.reader(io.StringIO(text)))
    callback(rows)
    output=io.StringIO(); csv.writer(output, delimiter=delimiter).writerows(rows)
    return output.getvalue()

def test_named_formats_exact_roundtrip(config):
    names = replace(config.names, players_a=('Имя, с запятой', 'Игрок "Б"', 'Иван'),
                    missions=('Миссия | особая', *config.names.missions[1:]))
    config = replace(config, names=names)
    for filename, data in [('input.csv',export_csv(config)), ('input.json',export_json(config))]:
        assert import_data(data.encode('utf-8-sig'),filename) == config

def test_template_has_names_ids_and_243_blanks():
    rows=list(csv.reader(io.StringIO(export_csv())))
    assert len(rows)==28 and len(rows[0])==15
    assert all(cell=='' for r in rows[1:] for cell in r[6:])
    assert len({(r[0],r[2],r[4]) for r in rows[1:]})==27
    assert all(r[1] and r[3] and r[5] for r in rows[1:])
    with pytest.raises(InvalidData,match='отсутствует'): import_data(export_csv(),'t.csv')

@pytest.mark.parametrize('kind', ['missing', 'duplicate', 'range', 'bad_id', 'names', 'mission_id', 'width'])
def test_bad_csv(config,kind):
    def change(rows):
        if kind=='missing': rows.pop()
        if kind=='duplicate': rows.append(rows[1])
        if kind=='range': rows[1][6]='21'
        if kind=='bad_id': rows[1][0]='no'
        if kind=='names': rows[2][1]='Несогласованное имя'
        if kind=='mission_id': rows[0][7]=rows[0][6]
        if kind=='width': rows[1].append('extra')
    with pytest.raises(InvalidData): import_data(rewrite(export_csv(config),change),'t.csv')

def test_excel_semicolon_decimal_comma(config):
    text=rewrite(export_csv(config),lambda rows: rows[1].__setitem__(6,'12,5'),delimiter=';')
    assert str(import_data(text,'t.csv').payoffs.data[0][0][0][0])=='25/2'

def test_decimal_export_does_not_round_or_turn_simple_fractions_into_dates():
    from fractions import Fraction as F
    from wtc_assistant.data import csv_number
    for value in (F(1,2),F(123,10),F(1,2**100),F(1,3),F(0),F(20)):
        assert F(csv_number(value))==value
    assert csv_number(F(1,2))=='0.5'

def test_legacy_formats(config):
    from pathlib import Path
    for path in ('examples/payoffs_demo.json',):
        assert import_data(Path(path).read_bytes(),path).payoffs==config.payoffs
    rows=[['player_a','player_b','table']+[f'M{i}' for i in range(9)]]
    for a in range(3):
        for b in range(3):
            for t in range(3): rows.append([a,b,t,*map(str,config.payoffs.data[a][b][t])])
    output=io.StringIO(); csv.writer(output).writerows(rows)
    assert import_data(output.getvalue(),'old.csv')==config

def test_invalid_json(config):
    for text in ('not json', '{}', 'null', '[]'):
        with pytest.raises(InvalidData): import_data(text,'bad.json')
    data=config.to_data(); data['version']=2
    with pytest.raises(InvalidData): import_data(json.dumps(data),'bad.json')

def test_names_are_validated():
    names=Names.defaults()
    with pytest.raises(InvalidData): replace(names,players_a=('A','A','B'))
    with pytest.raises(InvalidData): replace(names,tables=('','x','y'))
