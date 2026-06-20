

from __future__ import annotations

import os
import random
import sys
from typing import List, Optional, Tuple

from algorithms import (
    FCFSScheduler,
    PriorityScheduler,
    RoundRobinScheduler,
    SJFScheduler,
    SRTFScheduler,
)
from gantt_chart import (
    render_gantt_boxed,
    render_gantt_bracket,
    render_gantt_coloured,
    render_execution_slices,
)
from models import Process, SchedulingResult


WIDTH = 76

BOLD  = "\033[1m"
DIM   = "\033[2m"
RESET = "\033[0m"
CYAN  = "\033[96m"
GREEN = "\033[92m"
AMBER = "\033[93m"
RED   = "\033[91m"


def _supports_colour() -> bool:

    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


USE_COLOUR = _supports_colour()


def c(text: str, code: str) -> str:

    return f"{code}{text}{RESET}" if USE_COLOUR else text


def banner(title: str) -> None:
    print()
    print(c("=" * WIDTH, BOLD))
    print(c(f"  {title}", BOLD))
    print(c("=" * WIDTH, BOLD))


def section(title: str) -> None:
    print(f"\n{c('─' * WIDTH, DIM)}")
    print(f"  {c(title, BOLD)}")
    print(c("─" * WIDTH, DIM))


def info(msg: str) -> None:
    print(f"  {c('ℹ', CYAN)}  {msg}")


def ok(msg: str) -> None:
    print(f"  {c('✓', GREEN)}  {msg}")


def warn(msg: str) -> None:
    print(f"  {c('⚠', AMBER)}  {msg}")


def err(msg: str) -> None:
    print(f"  {c('✗', RED)}  {msg}")


def _prompt_int(prompt: str, min_val: int = 0, max_val: int = 10_000) -> int:

    while True:
        try:
            raw = input(f"  {prompt}: ").strip()
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            err(f"Please enter a value between {min_val} and {max_val}.")
        except (ValueError, EOFError):
            err("Invalid input.  Please enter a whole number.")


def _prompt_str(prompt: str, max_len: int = 20) -> str:

    while True:
        raw = input(f"  {prompt}: ").strip()
        if 1 <= len(raw) <= max_len:
            return raw
        err(f"Please enter 1–{max_len} characters.")


def input_processes_manually() -> List[Process]:

    section("Manual Process Entry")
    n = _prompt_int("Number of processes to add (1–20)", min_val=1, max_val=20)
    processes: List[Process] = []
    existing_pids: set = set()

    for i in range(1, n + 1):
        print(f"\n  {c(f'— Process {i} of {n} —', DIM)}")
        while True:
            default_pid = f"P{i}"
            raw_pid = input(f"  PID (default: {default_pid}): ").strip()
            pid = raw_pid if raw_pid else default_pid
            if pid in existing_pids:
                warn(f"PID '{pid}' already used.  Choose a different ID.")
            else:
                existing_pids.add(pid)
                break

        at  = _prompt_int("Arrival Time (≥ 0)", min_val=0, max_val=9_999)
        bt  = _prompt_int("Burst  Time (≥ 1)", min_val=1, max_val=9_999)
        pri = _prompt_int("Priority   (0 = highest; lower # = higher priority)",
                          min_val=0, max_val=100)
        processes.append(Process(pid=pid, arrival_time=at, burst_time=bt, priority=pri))
        ok(f"{pid} added  (AT={at}, BT={bt}, Priority={pri})")

    return processes


def generate_random_processes(existing_pids: Optional[set] = None) -> List[Process]:

    section("Random Workload Generation")
    n       = _prompt_int("Number of processes (1–20)", min_val=1, max_val=20)
    max_at  = _prompt_int("Maximum arrival time", min_val=0, max_val=500)
    min_bt  = _prompt_int("Minimum burst time", min_val=1, max_val=100)
    max_bt  = _prompt_int("Maximum burst time (≥ min burst time)",
                           min_val=min_bt, max_val=200)
    min_pri = _prompt_int("Minimum priority value", min_val=0, max_val=10)
    max_pri = _prompt_int("Maximum priority value (≥ min priority)",
                           min_val=min_pri, max_val=10)

    used = set(existing_pids) if existing_pids else set()
    processes: List[Process] = []
    counter = 1
    for _ in range(n):

        while f"P{counter}" in used:
            counter += 1
        pid = f"P{counter}"
        used.add(pid)
        counter += 1

        at  = random.randint(0, max_at)
        bt  = random.randint(min_bt, max_bt)
        pri = random.randint(min_pri, max_pri)
        processes.append(Process(pid=pid, arrival_time=at, burst_time=bt, priority=pri))

    ok(f"Generated {n} process(es).")
    return processes


def use_demo_processes() -> List[Process]:

    return [
        Process(pid="P1", arrival_time=0, burst_time=5, priority=2),
        Process(pid="P2", arrival_time=0, burst_time=3, priority=1),
        Process(pid="P3", arrival_time=2, burst_time=8, priority=4),
        Process(pid="P4", arrival_time=4, burst_time=6, priority=3),
        Process(pid="P5", arrival_time=6, burst_time=2, priority=5),
    ]


def select_algorithms(processes: List[Process]) -> Tuple[List, Optional[int]]:

    section("Algorithm Selection")
    print("""
    1.  First Come First Serve (FCFS)
    2.  Shortest Job First — Non-preemptive (SJF)
    3.  Round Robin (RR)
    4.  Priority Scheduling — Non-preemptive
    5.  Shortest Remaining Time First — Preemptive (SRTF)  [Advanced]
    6.  Run ALL algorithms
    """)
    choice = _prompt_int("Select option (1–6)", min_val=1, max_val=6)

    quantum: Optional[int] = None
    rr_needed = choice in (3, 6)
    if rr_needed:
        quantum = _prompt_int("\n  Round Robin: Time Quantum (≥ 1)", min_val=1, max_val=9_999)

    schedulers = []
    if choice in (1, 6):
        schedulers.append(FCFSScheduler(list(processes)))
    if choice in (2, 6):
        schedulers.append(SJFScheduler(list(processes)))
    if choice in (3, 6):
        schedulers.append(RoundRobinScheduler(list(processes), time_quantum=quantum))
    if choice in (4, 6):
        schedulers.append(PriorityScheduler(list(processes)))
    if choice in (5, 6):
        schedulers.append(SRTFScheduler(list(processes)))

    return schedulers, quantum


def print_process_table(processes: List[Process]) -> None:

    col_pid = max(5, max(len(p.pid) for p in processes))
    header = (
        f"  {'PID':<{col_pid}}  {'Arrival':>7}  {'Burst':>5}  {'Priority':>8}"
    )
    sep = "  " + "-" * (col_pid + 28)
    print(header)
    print(sep)
    for p in processes:
        print(
            f"  {p.pid:<{col_pid}}  {int(p.arrival_time):>7}  "
            f"{int(p.burst_time):>5}  {p.priority:>8}"
        )
    print()


def print_result(result: SchedulingResult, show_slices: bool = False) -> None:

    banner(f"Algorithm: {result.algorithm_name}")

    print(f"\n  {c('Gantt Chart (bracket):', BOLD)}")
    print(f"  {render_gantt_bracket(result.gantt_chart)}")

    if USE_COLOUR:
        print(f"\n  {c('Gantt Chart (coloured):', BOLD)}")
        print(f"  {render_gantt_coloured(result.gantt_chart)}")

    print(f"\n  {c('Gantt Chart (boxed):', BOLD)}")

    for line in render_gantt_boxed(result.gantt_chart).splitlines():
        print(f"  {line}")

    if show_slices:
        print(f"\n  {c('Execution Slices per Process:', BOLD)}")
        for line in render_execution_slices(result.gantt_chart).splitlines():
            print(f"  {line}")

    print(f"\n  {c('Process Metrics:', BOLD)}")
    for line in result.summary_table().splitlines():
        print(f"  {line}")
    print()


def print_comparison(results: List[SchedulingResult]) -> None:

    banner("Performance Comparison Summary")
    col_alg = max(len(r.algorithm_name) for r in results)
    col_alg = max(col_alg, 45)
    header = f"  {'Algorithm':<{col_alg}}  {'Avg WT':>8}  {'Avg TAT':>9}"
    sep = "  " + "-" * (col_alg + 22)
    print(header)
    print(sep)
    for r in results:
        print(
            f"  {r.algorithm_name:<{col_alg}}  "
            f"{r.average_waiting_time:>8.2f}  "
            f"{r.average_turnaround_time:>9.2f}"
        )
    print(sep)

    best_wt = min(results, key=lambda r: r.average_waiting_time)
    best_tat = min(results, key=lambda r: r.average_turnaround_time)
    ok(f"Lowest Avg WT  : {best_wt.algorithm_name}  ({best_wt.average_waiting_time:.2f})")
    ok(f"Lowest Avg TAT : {best_tat.algorithm_name}  ({best_tat.average_turnaround_time:.2f})")
    print()


def offer_csv_export(results: List[SchedulingResult]) -> None:

    section("Export Results to CSV")
    raw = input("  Export results to CSV files? (y/N): ").strip().lower()
    if raw not in ("y", "yes"):
        info("Skipped export.")
        return

    export_dir = input("  Export directory (default: current folder): ").strip()
    if not export_dir:
        export_dir = "."
    os.makedirs(export_dir, exist_ok=True)

    for result in results:
        safe_name = (
            result.algorithm_name
            .replace(" ", "_")
            .replace(",", "")
            .replace("(", "")
            .replace(")", "")
            .replace("=", "")
        )
        filepath = os.path.join(export_dir, f"{safe_name}.csv")
        result.export_csv(filepath)
        ok(f"Saved: {filepath}")


def main() -> None:
    banner("CPU Scheduling Simulator")
    print("""
  Implements:
    • First Come First Serve (FCFS)
    • Shortest Job First — Non-preemptive (SJF)
    • Round Robin (RR)  — configurable time quantum
    • Priority Scheduling — Non-preemptive
    • Shortest Remaining Time First (SRTF)  [Advanced Feature]

  Formulas applied:
    TAT = Completion Time − Arrival Time
    WT  = Turnaround Time − Burst Time
""")


    section("Process Input Method")
    print("""
    1.  Enter processes manually
    2.  Generate random workload
    3.  Use built-in demo dataset
    """)
    input_choice = _prompt_int("Select option (1–3)", min_val=1, max_val=3)

    if input_choice == 1:
        processes = input_processes_manually()
    elif input_choice == 2:
        processes = generate_random_processes()
    else:
        processes = use_demo_processes()
        info("Using built-in demo dataset.")


    section("Process List")
    print_process_table(processes)


    schedulers, _quantum = select_algorithms(processes)


    show_slices_raw = input("\n  Show per-slice execution detail? (y/N): ").strip().lower()
    show_slices = show_slices_raw in ("y", "yes")


    results: List[SchedulingResult] = []
    for scheduler in schedulers:
        try:
            result = scheduler.run()
            results.append(result)
            print_result(result, show_slices=show_slices)
        except Exception as exc:
            err(f"Failed to run {scheduler.algorithm_name}: {exc}")


    if len(results) > 1:
        print_comparison(results)


    if results:
        offer_csv_export(results)

    banner("Simulation Complete")


if __name__ == "__main__":
    main()

