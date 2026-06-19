"""
main.py
=======
Phase 3 (part 2): Driver code.

This script:
  1. Defines a small mock dataset of processes (with varying arrival
     times, burst times, and priorities, including a couple of
     simultaneous arrivals to exercise tie-breaking logic).
  2. Runs that dataset through all four required algorithms:
       FCFS, SJF, Round Robin (quantum=4), Priority.
  3. Prints, for each algorithm: the text-based Gantt chart, the
     per-process metrics table, and the two required averages.

Run with:
    python3 main.py

This file is intentionally the ONLY place in the codebase that "knows
about" all four algorithms by name -- everything in algorithms.py is
independent and reusable. A GUI would replace this file's job (not
algorithms.py's), by calling the same Scheduler.run() interface from
button callbacks instead of from a linear script.
"""

from __future__ import annotations

from typing import List

from algorithms import (
    FCFSScheduler,
    PriorityScheduler,
    RoundRobinScheduler,
    SJFScheduler,
)
from gantt_chart import render_gantt_chart, render_gantt_chart_boxed
from models import Process, Scheduler, SchedulingResult


def build_sample_processes() -> List[Process]:
    """
    Builds a small, hand-crafted dataset designed to exercise interesting
    edge cases when run through any of the four algorithms:

      - P1 and P2 arrive at the SAME time (t=0) -> tests tie-breaking.
      - There is a gap between P2's arrival (t=0) and P3's arrival (t=2)
        relative to short burst times -> can create CPU idle time
        depending on the algorithm.
      - Burst times vary widely (3 to 9) -> SJF ordering is non-trivial.
      - Priorities are deliberately NOT correlated with arrival or burst
        time, so Priority Scheduling visibly reorders things compared to
        FCFS/SJF.

    Returns
    -------
    List[Process]
        A fresh list of Process objects. A fresh list (not the same
        objects reused) is rebuilt for the demo to keep main() simple to
        read, even though Scheduler.run() would also work correctly on
        a single reused list thanks to reset_for_simulation().
    """
    return [
        Process(pid="P1", arrival_time=0, burst_time=5, priority=2),
        Process(pid="P2", arrival_time=0, burst_time=3, priority=1),
        Process(pid="P3", arrival_time=2, burst_time=8, priority=4),
        Process(pid="P4", arrival_time=4, burst_time=6, priority=3),
        Process(pid="P5", arrival_time=6, burst_time=2, priority=5),
    ]


def print_result(result: SchedulingResult) -> None:
    """
    Pretty-prints a single SchedulingResult: algorithm name, both Gantt
    chart renderings, the metrics table, and the two required averages
    (the latter two are already included inside summary_table()).
    """
    print("=" * 70)
    print(f"Algorithm: {result.algorithm_name}")
    print("=" * 70)

    print("\nGantt Chart (bracket form):")
    print(render_gantt_chart(result.gantt_chart))

    print("\nGantt Chart (boxed form):")
    print(render_gantt_chart_boxed(result.gantt_chart))

    print("\nProcess Metrics:")
    print(result.summary_table())
    print()


def main() -> None:
    print("CPU SCHEDULING SIMULATOR")
    print("Sample dataset:")
    sample = build_sample_processes()
    print(f"{'PID':<6}{'AT':<6}{'BT':<6}{'Priority':<10}")
    for p in sample:
        print(f"{p.pid:<6}{p.arrival_time:<6}{p.burst_time:<6}{p.priority:<10}")
    print()

    # Each scheduler gets the SAME underlying Process objects. This is
    # safe and intentional: Scheduler.run() calls reset_for_simulation()
    # on every process before it starts, so results never leak between
    # algorithms despite reusing the list.
    schedulers: List[Scheduler] = [
        FCFSScheduler(sample),
        SJFScheduler(sample),
        RoundRobinScheduler(sample, time_quantum=4),
        PriorityScheduler(sample),
    ]

    results = []
    for scheduler in schedulers:
        result = scheduler.run()
        results.append(result)
        print_result(result)

    # A quick side-by-side comparison of averages across all four
    # algorithms -- directly useful for the "Performance Comparison"
    # section the report template requires.
    print("=" * 70)
    print("PERFORMANCE COMPARISON SUMMARY")
    print("=" * 70)
    print(f"{'Algorithm':<45}{'Avg WT':<12}{'Avg TAT':<12}")
    for result in results:
        print(
            f"{result.algorithm_name:<45}"
            f"{result.average_waiting_time:<12.2f}"
            f"{result.average_turnaround_time:<12.2f}"
        )


if __name__ == "__main__":
    main()
