"""Validated tensor and file input. Rules do not depend on this module."""
import csv
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from .models import InvalidData, Match

def rational(value: int | float | str | Fraction | Decimal) -> Fraction:
    """Decimal floats use their shortest decimal spelling, not binary expansion."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Fraction, Decimal)):
        raise InvalidData(f"Expected a rational number, got {value!r}")
    try:
        return Fraction(str(value)) if isinstance(value, (float, Decimal)) else Fraction(value)
    except (ValueError, ZeroDivisionError, OverflowError) as exc:
        raise InvalidData(f"Invalid finite rational: {value!r}") from exc

@dataclass(frozen=True, slots=True, init=False)
class Payoffs:
    data: tuple

    def __init__(self, tensor):
        def convert(x, dims):
            if not dims:
                q = rational(x)
                if not 0 <= q <= 20:
                    raise InvalidData("Expected GP must lie in [0, 20]")
                return q
            if not isinstance(x, (list, tuple)) or len(x) != dims[0]:
                raise InvalidData("Expected tensor dimensions [3][3][3][9]")
            return tuple(convert(y, dims[1:]) for y in x)
        object.__setattr__(self, "data", convert(tensor, (3, 3, 3, 9)))

    def gp(self, match: Match) -> Fraction:
        return self.data[match.a][match.b][match.table][match.mission]

    def to_list(self) -> list:
        return [[[[str(v) for v in row] for row in b] for b in a] for a in self.data]

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.to_list(), separators=(",", ":")).encode()).hexdigest()

    def swapped(self) -> 'Payoffs':
        return Payoffs([[[[20-self.data[b][a][t][m] for m in range(9)]
                          for t in range(3)] for b in range(3)] for a in range(3)])

def load_payoffs(path) -> Payoffs:
    """Read tensor JSON or wide CSV: player_a,player_b,table,M0,...,M8."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        try:
            return Payoffs(json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal))
        except (ValueError, OSError) as exc:
            raise InvalidData(f"Cannot load tensor: {exc}") from exc
    if path.suffix.lower() != ".csv":
        raise InvalidData("Use JSON or CSV; export the GP worksheet as CSV first")
    tensor = [[[[None]*9 for _ in range(3)] for _ in range(3)] for _ in range(3)]
    seen = set()
    try:
        with path.open(encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != ["player_a", "player_b", "table"] + [f"M{i}" for i in range(9)]:
                raise InvalidData("Unexpected CSV columns")
            for row in reader:
                ids = tuple(int(row[k]) for k in ("player_a", "player_b", "table"))
                if any(i not in range(3) for i in ids) or ids in seen or None in row:
                    raise InvalidData("Invalid or duplicate CSV identifiers")
                seen.add(ids)
                a,b,t = ids
                tensor[a][b][t] = [row[f"M{i}"] for i in range(9)]
        if len(seen) != 27:
            raise InvalidData("CSV requires all 27 matchup/table rows")
        return Payoffs(tensor)
    except (ValueError, TypeError, KeyError) as exc:
        raise InvalidData(f"Invalid CSV: {exc}") from exc

def benchmark_payoffs():
    """Fixed integer tensor; no random library/version dependency."""
    return Payoffs([[[[(a*71+b*43+t*29+m*17+a*b*11+t*m*7+a*m*m*3)%21
                      for m in range(9)] for t in range(3)] for b in range(3)] for a in range(3)])
