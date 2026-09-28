"""Version 1 canonical JSON, rational strings, SHA-256 corruption detection.

Checksums detect accidental corruption, not malicious replacement. Loading
checks all equilibrium certificates by default, without solving any matrix LP.
"""
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from .models import InvalidData, Node, Position, Stage
from .payoff import Payoffs, rational
from .policy import Solution

VERSION = 1
POLICY_RULE = 'mean-distinct-optimal-vertices-v1'

def canonical(data):
    return json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=True)

def pack(kind, data):
    body = dict(version=VERSION,kind=kind,data=data)
    return canonical(dict(body=body,sha256=hashlib.sha256(canonical(body).encode()).hexdigest()))

def unpack(text, kind):
    try:
        doc = json.loads(text)
        body = doc['body']
        if body['version'] != VERSION or type(body['version']) is not int or body['kind'] != kind:
            raise InvalidData("Incompatible format version or document type")
        if hashlib.sha256(canonical(body).encode()).hexdigest() != doc['sha256']:
            raise InvalidData("Checksum mismatch")
        return body['data']
    except (KeyError,TypeError,ValueError) as exc:
        raise InvalidData(f"Invalid serialized document: {exc}") from exc

def position_data(p):
    return [int(p.stage),list(p.missions),list(p.tables),list(p.shields),[list(x) for x in p.pairs],p.table]

def read_position(x):
    if len(x)!=6:
        raise InvalidData("Invalid position record")
    s,m,t,h,p,chosen = x
    flat = [s,*m,*t,*h,*(v for pair in p for v in pair),chosen]
    if any(type(v) is not int for v in flat) or any(len(pair)!=2 for pair in p):
        raise InvalidData("Position identifiers must be integers")
    return Position(Stage(s),tuple(m),tuple(t),tuple(h),tuple(tuple(pair) for pair in p),chosen)

def dumps(solution):
    records = [[position_data(p),str(n.value),list(map(str,n.a)),list(map(str,n.b))]
               for p,n in solution.nodes.items()]
    records.sort(key=lambda r:canonical(r[0]))
    return pack('solution',dict(policy_rule=POLICY_RULE,tensor=solution.payoffs.to_list(),
                tensor_sha256=solution.payoffs.fingerprint,attacker=solution.attacker_team,
                nodes=records,statistics=dict(solution.statistics)))

def loads(text, expected_payoffs=None):
    from .verify import verify_solution
    try:
        data = unpack(text,'solution')
        if data['policy_rule'] != POLICY_RULE:
            raise InvalidData("Incompatible policy selection rule")
        payoffs = Payoffs(data['tensor'])
        if payoffs.fingerprint != data['tensor_sha256']:
            raise InvalidData("Tensor checksum mismatch")
        if expected_payoffs is not None and payoffs.fingerprint != expected_payoffs.fingerprint:
            raise InvalidData("Input tensor mismatch")
        nodes = {}
        for p,v,a,b in data['nodes']:
            p = read_position(p)
            if p in nodes:
                raise InvalidData("Duplicate policy node")
            nodes[p] = Node(rational(v),tuple(map(rational,a)),tuple(map(rational,b)))
        result = Solution(payoffs,data['attacker'],MappingProxyType(nodes),MappingProxyType(data['statistics']))
        verify_solution(result)
        return result
    except (KeyError,TypeError,ValueError,AssertionError,IndexError) as exc:
        raise InvalidData(f"Invalid policy: {exc}") from exc

def save(solution,path):
    Path(path).write_text(dumps(solution),encoding='utf-8')

def load(path,expected_payoffs=None):
    return loads(Path(path).read_text(encoding='utf-8'),expected_payoffs)
