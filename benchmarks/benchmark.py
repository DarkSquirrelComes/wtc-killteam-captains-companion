"""Standalone reproducible benchmark; deliberately outside pytest discovery.

Solve-time pass uses no memory instrumentation. A second separate solve under
tracemalloc measures Python allocation peak; Windows process peak working set
is additionally captured in isolated per-role worker processes when available.
"""
import argparse
import ctypes
import gc
import json
import platform
import subprocess
import sys
import tracemalloc
from pathlib import Path
from time import perf_counter
from wtc_solver import solve
from wtc_solver.payoff import benchmark_payoffs
from wtc_solver.serialization import dumps
from wtc_solver.verify import verify_solution

def process_peak_bytes():
    if sys.platform=='win32':
        class Counters(ctypes.Structure):
            _fields_=[('cb',ctypes.c_ulong),('PageFaultCount',ctypes.c_ulong)]+[
                (n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize',
                'QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        c=Counters(); c.cb=ctypes.sizeof(c)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype=ctypes.c_void_p
        psapi=ctypes.WinDLL('psapi',use_last_error=True)
        psapi.GetProcessMemoryInfo.argtypes=[ctypes.c_void_p,ctypes.POINTER(Counters),ctypes.c_ulong]
        if psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):
            return c.PeakWorkingSetSize
    return None

def worker(role):
    payoffs=benchmark_payoffs()
    start=perf_counter(); s=solve(payoffs,role); elapsed=perf_counter()-start
    solve_process_peak=process_peak_bytes()
    stats=dict(s.statistics)
    validation=verify_solution(s)
    data=dumps(s)
    n=2000; start=perf_counter()
    for _ in range(n): s.get_recommendation((),s.rules.defender)
    query=(perf_counter()-start)/n
    result=dict(attacker=role,value_a=str(s.get_value().team_a),solve_seconds=elapsed,
                process_peak_working_set_bytes=solve_process_peak,
                serialized_bytes=len(data.encode()),query_mean_seconds=query,
                policy_nodes=len(s.nodes),statistics=stats,verification=validation)
    del s,data; gc.collect()
    tracemalloc.start()
    measured=solve(payoffs,role)
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result['python_allocation_peak_bytes']=peak
    result['instrumented_solve_seconds']=measured.statistics['solve_seconds']
    return result

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',choices=['A','B'])
    parser.add_argument('--output',default='outputs/benchmark.json')
    args=parser.parse_args()
    if args.worker:
        print(json.dumps(worker(args.worker))); return
    results=[]
    for role in ('A','B'):
        process=subprocess.run([sys.executable,__file__,'--worker',role],check=True,capture_output=True,text=True)
        results.append(json.loads(process.stdout))
        print(f'Attacker {role}: {results[-1]["solve_seconds"]:.3f}s',flush=True)
    report=dict(python=sys.version,platform=platform.platform(),tensor_sha256=benchmark_payoffs().fingerprint,
                terminal_sequences_per_role=3265920,results=results)
    path=Path(args.output); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__': main()
