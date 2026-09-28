"""Stable positional IDs and display names live outside the solver."""
from dataclasses import dataclass
from wtc_solver import InvalidData, Payoffs

@dataclass(frozen=True, slots=True)
class Names:
    players_a: tuple[str, ...]
    players_b: tuple[str, ...]
    tables: tuple[str, ...]
    missions: tuple[str, ...]

    def __post_init__(self):
        for key, size in [('players_a', 3), ('players_b', 3), ('tables', 3), ('missions', 9)]:
            values = getattr(self, key)
            if not isinstance(values, tuple) or len(values) != size:
                raise InvalidData(f'{key}: требуется {size} названий.')
            if any(not isinstance(v, str) or not v.strip() or len(v) > 200 for v in values):
                raise InvalidData(f'{key}: названия должны быть непустыми строками до 200 символов.')
            if any(v != v.strip() or any(c in v for c in '\r\n\x00') for v in values):
                raise InvalidData(f'{key}: уберите переносы строк и пробелы по краям названий.')
            if len(set(values)) != size:
                raise InvalidData(f'{key}: используйте различимые названия внутри одной группы.')

    @classmethod
    def defaults(cls):
        return cls(tuple(f'Наш игрок {i+1}' for i in range(3)),
                   tuple(f'Соперник {i+1}' for i in range(3)),
                   tuple(f'Стол {i+1}' for i in range(3)),
                   tuple(f'Миссия {i+1}' for i in range(9)))

    def to_data(self):
        return {k: list(getattr(self, k)) for k in ('players_a', 'players_b', 'tables', 'missions')}

    @classmethod
    def from_data(cls, data):
        try:
            if set(data) != {'players_a', 'players_b', 'tables', 'missions'}:
                raise InvalidData('Неверные группы названий.')
            return cls(**{k: tuple(v) for k,v in data.items()})
        except (KeyError, TypeError) as exc:
            raise InvalidData('Неверный справочник названий.') from exc

@dataclass(frozen=True, slots=True)
class Configuration:
    payoffs: Payoffs
    names: Names

    def to_data(self):
        return dict(format='wtc-input', version=1, names=self.names.to_data(), tensor=self.payoffs.to_list())

    @classmethod
    def from_data(cls, data):
        try:
            if data['format'] != 'wtc-input' or type(data['version']) is not int or data['version'] != 1:
                raise InvalidData('Несовместимая версия входного файла.')
            return cls(Payoffs(data['tensor']), Names.from_data(data['names']))
        except (KeyError, TypeError) as exc:
            raise InvalidData('Неполная конфигурация: нужны names и tensor.') from exc
