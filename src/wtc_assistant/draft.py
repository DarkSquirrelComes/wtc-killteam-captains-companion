"""UI-independent, exact, partially filled input with transactional undo."""
from dataclasses import dataclass, replace
from fractions import Fraction
import json
from wtc_solver import Payoffs
from wtc_solver.payoff import rational
from .config import Configuration, Names


def cell(value):
    if value is None or value == '':
        return None
    result = rational(value)
    if not 0 <= result <= 20:
        raise ValueError('Оценки должны быть от 0 до 20.')
    return result


def index(a, b, t, m):
    if any(type(v) is not int or not 0 <= v < size for v, size in zip((a,b,t,m),(3,3,3,9))):
        raise ValueError('Недопустимая ячейка.')
    return ((a*3+b)*3+t)*9+m


@dataclass(frozen=True)
class Draft:
    names: Names
    cells: tuple[Fraction | None, ...] = (None,)*243

    def __post_init__(self):
        if len(self.cells) != 243:
            raise ValueError('Нужно 243 ячейки.')
        object.__setattr__(self, 'cells', tuple(cell(v) for v in self.cells))

    @classmethod
    def from_config(cls, config):
        return cls(config.names, tuple(config.payoffs.data[a][b][t][m]
                   for a in range(3) for b in range(3) for t in range(3) for m in range(9)))

    @property
    def filled(self): return sum(v is not None for v in self.cells)

    def get(self,a,b,t,m): return self.cells[index(a,b,t,m)]

    def edit(self, changes):
        values = list(self.cells)
        for coords, value in changes:
            values[index(*coords)] = cell(value)
        return replace(self, cells=tuple(values))

    def region(self,a,b,axis='all',target=0):
        return tuple((a,b,t,m) for t in range(3) for m in range(9)
                     if axis == 'all' or axis == 'mission' and m == target or axis == 'table' and t == target)

    def bulk(self,a,b,axis,target,operation,value=None,source=0):
        if axis not in ('all','mission','table'):
            raise ValueError('Неизвестная область.')
        coords = self.region(a,b,axis,target)
        if not coords: raise ValueError('Пустая область.')
        changes=[]
        for ca,cb,t,m in coords:
            old=self.get(ca,cb,t,m)
            if operation == 'fill': new=value
            elif operation == 'clear': new=None
            elif operation == 'shift': new=None if old is None else old+rational(value)
            elif operation == 'copy':
                new=(self.get(source//3,source%3,t,m) if axis == 'all' else
                     self.get(a,b,source,m) if axis == 'table' else self.get(a,b,t,source))
            else: raise ValueError('Неизвестная операция.')
            changes.append(((ca,cb,t,m),new))
        return self.edit(changes)

    def configuration(self):
        if self.filled != 243: raise ValueError('Заполните все 243 оценки.')
        return Configuration(Payoffs([[[[self.get(a,b,t,m) for m in range(9)]
                             for t in range(3)] for b in range(3)] for a in range(3)]),self.names)

    def dumps(self):
        return json.dumps(dict(format='wtc-draft', version=1, names=self.names.to_data(),
                               cells=[None if v is None else str(v) for v in self.cells]),ensure_ascii=False)

    @classmethod
    def loads(cls,text):
        try:
            data=json.loads(text)
            if data['format'] != 'wtc-draft' or type(data['version']) is not int or data['version'] != 1:
                raise ValueError('Несовместимый черновик.')
            return cls(Names.from_data(data['names']),tuple(data['cells']))
        except (KeyError,TypeError) as exc:
            raise ValueError('Повреждённый черновик.') from exc
