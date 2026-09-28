import argparse
import json
from pathlib import Path
from .payoff import load_payoffs
from .serialization import load,save
from .solver import solve
from .verify import verify_solution

def main(argv=None):
    parser=argparse.ArgumentParser(description='Exact WTC 3x3 pairing solver')
    sub=parser.add_subparsers(dest='command',required=True)
    s=sub.add_parser('solve')
    s.add_argument('tensor',type=Path)
    s.add_argument('--output',type=Path,default=Path('outputs/policies'))
    v=sub.add_parser('verify')
    v.add_argument('policy',type=Path)
    args=parser.parse_args(argv)
    if args.command=='verify':
        solution=load(args.policy)
        print(json.dumps(verify_solution(solution),indent=2))
    else:
        payoffs=load_payoffs(args.tensor)
        args.output.mkdir(parents=True,exist_ok=True)
        for role in ('A','B'):
            solution=solve(payoffs,role)
            certificate=verify_solution(solution)
            save(solution,args.output/f'attacker_{role}.json')
            print(json.dumps(dict(attacker=role,value_a=str(solution.get_value().team_a),
                                 statistics=dict(solution.statistics),verified=certificate),indent=2))

if __name__=='__main__':
    main()
