"""
edge_case_checks.py
====================
Quick sanity-check script (not a formal unit test suite) exercising the
edge cases described in Phase 4: idle CPU time, simultaneous arrivals,
a single process, and a quantum larger than every burst time (which
should make Round Robin behave identically to FCFS).

Run with:
    python3 edge_case_checks.py
"""

from algorithms import FCFSScheduler, PriorityScheduler, RoundRobinScheduler, SJFScheduler
from gantt_chart import render_gantt_chart
from models import Process


def check_idle_time():
    print("--- CHECK 1: CPU idle time (gap before first arrival) ---")
    procs = [
        Process("P1", arrival_time=5, burst_time=3),
        Process("P2", arrival_time=10, burst_time=2),
    ]
    result = FCFSScheduler(procs).run()
    print(render_gantt_chart(result.gantt_chart))
    assert result.gantt_chart[0].process_id == "IDLE"
    assert result.gantt_chart[0].start == 0 and result.gantt_chart[0].end == 5
    print("PASS: idle gap correctly recorded from t=0 to t=5.\n")


def check_simultaneous_arrivals_tiebreak():
    print("--- CHECK 2: Simultaneous arrivals tie-break (PID order) ---")
    procs = [
        Process("P3", arrival_time=0, burst_time=2),
        Process("P1", arrival_time=0, burst_time=2),
        Process("P2", arrival_time=0, burst_time=2),
    ]
    result = FCFSScheduler(procs).run()
    order = [e.process_id for e in result.gantt_chart]
    print(order)
    assert order == ["P1", "P2", "P3"], "Tie-break should default to PID order"
    print("PASS: ties broken consistently by PID.\n")


def check_single_process():
    print("--- CHECK 3: Single process (no contention at all) ---")
    procs = [Process("P1", arrival_time=0, burst_time=4)]
    for cls, kwargs in [
        (FCFSScheduler, {}),
        (SJFScheduler, {}),
        (PriorityScheduler, {}),
        (RoundRobinScheduler, {"time_quantum": 2}),
    ]:
        result = cls(procs, **kwargs).run() if kwargs else cls(procs).run()
        p = result.processes[0]
        assert p.completion_time == 4
        assert p.waiting_time == 0
        assert p.turnaround_time == 4
    print("PASS: single process yields WT=0, TAT=BT for every algorithm.\n")


def check_large_quantum_equals_fcfs():
    print("--- CHECK 4: RR with huge quantum behaves like FCFS ---")
    procs_rr = [
        Process("P1", arrival_time=0, burst_time=3),
        Process("P2", arrival_time=1, burst_time=4),
        Process("P3", arrival_time=2, burst_time=2),
    ]
    procs_fcfs = [
        Process("P1", arrival_time=0, burst_time=3),
        Process("P2", arrival_time=1, burst_time=4),
        Process("P3", arrival_time=2, burst_time=2),
    ]
    rr_result = RoundRobinScheduler(procs_rr, time_quantum=999).run()
    fcfs_result = FCFSScheduler(procs_fcfs).run()

    rr_metrics = [(p.pid, p.waiting_time, p.turnaround_time) for p in rr_result.processes]
    fcfs_metrics = [(p.pid, p.waiting_time, p.turnaround_time) for p in fcfs_result.processes]
    print("RR  :", rr_metrics)
    print("FCFS:", fcfs_metrics)
    assert rr_metrics == fcfs_metrics
    print("PASS: oversized quantum makes RR collapse to FCFS, as expected.\n")


def check_waiting_time_conservation():
    print("--- CHECK 5: WT = TAT - BT and TAT = CT - AT, for every algorithm ---")
    procs = [
        Process("P1", arrival_time=0, burst_time=5, priority=2),
        Process("P2", arrival_time=1, burst_time=3, priority=1),
        Process("P3", arrival_time=2, burst_time=8, priority=3),
    ]
    for cls, kwargs in [
        (FCFSScheduler, {}),
        (SJFScheduler, {}),
        (PriorityScheduler, {}),
        (RoundRobinScheduler, {"time_quantum": 3}),
    ]:
        result = cls(procs, **kwargs).run() if kwargs else cls(procs).run()
        for p in result.processes:
            assert p.turnaround_time == p.completion_time - p.arrival_time
            assert p.waiting_time == p.turnaround_time - p.burst_time
    print("PASS: formulas hold exactly for every process, every algorithm.\n")


if __name__ == "__main__":
    check_idle_time()
    check_simultaneous_arrivals_tiebreak()
    check_single_process()
    check_large_quantum_equals_fcfs()
    check_waiting_time_conservation()
    print("ALL EDGE-CASE CHECKS PASSED.")
