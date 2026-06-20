

from __future__ import annotations

import csv
import os
import random
import sys
import unittest
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


@dataclass
class GanttEntry:

    process_id: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Process:


    pid: str
    arrival_time: float
    burst_time: float
    priority: int = 0

    remaining_time: float = field(init=False, default=0.0)
    completion_time: Optional[float] = field(init=False, default=None)
    waiting_time: Optional[float] = field(init=False, default=None)
    turnaround_time: Optional[float] = field(init=False, default=None)
    response_time: Optional[float] = field(init=False, default=None)
    execution_history: List[GanttEntry] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.arrival_time, (int, float)):
            raise TypeError(f"[{self.pid}] arrival_time must be numeric.")
        if not isinstance(self.burst_time, (int, float)):
            raise TypeError(f"[{self.pid}] burst_time must be numeric.")
        if self.arrival_time < 0:
            raise ValueError(f"[{self.pid}] arrival_time cannot be negative.")
        if self.burst_time <= 0:
            raise ValueError(f"[{self.pid}] burst_time must be > 0.")
        if not isinstance(self.priority, int):
            raise TypeError(f"[{self.pid}] priority must be an integer.")
        if self.priority < 0:
            raise ValueError(f"[{self.pid}] priority cannot be negative.")
        self.remaining_time = float(self.burst_time)

    def reset_for_simulation(self) -> None:

        self.remaining_time = float(self.burst_time)
        self.completion_time = None
        self.waiting_time = None
        self.turnaround_time = None
        self.response_time = None
        self.execution_history = []

    def record_execution(self, start: float, end: float) -> None:

        if end <= start:
            raise ValueError(f"[{self.pid}] Invalid slice: start={start}, end={end}.")
        if self.response_time is None:
            self.response_time = start - self.arrival_time
        self.execution_history.append(GanttEntry(self.pid, start, end))
        self.remaining_time -= (end - start)
        if self.remaining_time < -1e-9:
            raise RuntimeError(
                f"[{self.pid}] remaining_time went negative ({self.remaining_time:.6f})."
            )
        if abs(self.remaining_time) < 1e-9:
            self.remaining_time = 0.0

    @property
    def is_complete(self) -> bool:
        return self.remaining_time == 0.0

    def finalize_metrics(self, completion_time: float) -> None:

        self.completion_time = completion_time
        self.turnaround_time = self.completion_time - self.arrival_time
        self.waiting_time = self.turnaround_time - self.burst_time
        if self.waiting_time < -1e-9:
            raise RuntimeError(
                f"[{self.pid}] Negative waiting time ({self.waiting_time:.6f}). "
                f"Check scheduler logic."
            )

    def __repr__(self) -> str:
        return (
            f"Process(pid={self.pid!r}, AT={self.arrival_time}, "
            f"BT={self.burst_time}, priority={self.priority}, "
            f"remaining={self.remaining_time}, CT={self.completion_time})"
        )


@dataclass
class SchedulingResult:

    algorithm_name: str
    processes: List[Process]
    gantt_chart: List[GanttEntry]
    average_waiting_time: float
    average_turnaround_time: float

    def summary_table(self) -> str:

        if not self.processes:
            return "(no processes)"
        col_pid = max(5, max(len(p.pid) for p in self.processes))
        cols    = [col_pid, 6, 6, 10, 6, 6, 6, 13]
        headers = ["PID", "AT", "BT", "Priority", "CT", "TAT", "WT", "Response"]

        def row(*values) -> str:
            return "  ".join(str(v).ljust(w) for v, w in zip(values, cols))

        def fmt(x: Optional[float]) -> str:
            if x is None:
                return "?"
            return str(int(x)) if x == int(x) else f"{x:.2f}"

        sep = "-" * (sum(cols) + 2 * (len(cols) - 1))
        lines = [row(*headers), sep]
        for p in self.processes:
            lines.append(row(
                p.pid, fmt(p.arrival_time), fmt(p.burst_time), p.priority,
                fmt(p.completion_time), fmt(p.turnaround_time),
                fmt(p.waiting_time), fmt(p.response_time),
            ))
        lines.append(sep)
        lines.append(f"  Average Waiting Time    : {self.average_waiting_time:.2f}")
        lines.append(f"  Average Turnaround Time : {self.average_turnaround_time:.2f}")
        return "\n".join(lines)

    def export_csv(self, filepath: str) -> None:

        fieldnames = [
            "PID", "ArrivalTime", "BurstTime", "Priority",
            "CompletionTime", "TurnaroundTime", "WaitingTime", "ResponseTime",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for p in self.processes:
                writer.writerow({
                    "PID": p.pid,
                    "ArrivalTime": p.arrival_time,
                    "BurstTime": p.burst_time,
                    "Priority": p.priority,
                    "CompletionTime": p.completion_time,
                    "TurnaroundTime": p.turnaround_time,
                    "WaitingTime": p.waiting_time,
                    "ResponseTime": p.response_time,
                })


class Scheduler(ABC):


    def __init__(self, processes: List[Process]) -> None:
        if not processes:
            raise ValueError("Scheduler requires at least one process.")
        seen_pids: set = set()
        duplicates: set = set()
        for p in processes:
            if p.pid in seen_pids:
                duplicates.add(p.pid)
            seen_pids.add(p.pid)
        if duplicates:
            names = ", ".join(sorted(duplicates))
            raise ValueError(
                f"Duplicate process ID(s) found: {names}. "
                f"Every process must have a unique PID."
            )
        self.processes: List[Process] = processes

    @property
    @abstractmethod
    def algorithm_name(self) -> str:

        ...

    @abstractmethod
    def _execute(self) -> List[GanttEntry]:

        ...

    def run(self) -> SchedulingResult:

        for p in self.processes:
            p.reset_for_simulation()

        gantt = self._execute()

        unfinished = [p for p in self.processes if p.completion_time is None]
        if unfinished:
            names = ", ".join(p.pid for p in unfinished)
            raise RuntimeError(
                f"{self.algorithm_name}: unfinished processes: {names}."
            )

        n = len(self.processes)
        return SchedulingResult(
            algorithm_name=self.algorithm_name,
            processes=list(self.processes),
            gantt_chart=gantt,
            average_waiting_time=sum(p.waiting_time for p in self.processes) / n,
            average_turnaround_time=sum(p.turnaround_time for p in self.processes) / n,
        )


class FCFSScheduler(Scheduler):


    @property
    def algorithm_name(self) -> str:
        return "First Come First Serve (FCFS)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        ordered = sorted(self.processes, key=lambda p: (p.arrival_time, p.pid))
        clock: float = 0.0

        for process in ordered:
            if clock < process.arrival_time:
                gantt.append(GanttEntry("IDLE", clock, process.arrival_time))
                clock = process.arrival_time

            start, end = clock, clock + process.burst_time
            process.record_execution(start, end)
            gantt.append(GanttEntry(process.pid, start, end))
            clock = end
            process.finalize_metrics(clock)

        return gantt


class SJFScheduler(Scheduler):


    @property
    def algorithm_name(self) -> str:
        return "Shortest Job First (SJF, Non-preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        pool: List[Process] = list(self.processes)
        clock: float = 0.0
        completed: int = 0

        while completed < len(self.processes):
            ready = [p for p in pool if p.arrival_time <= clock]
            if not ready:
                next_arr = min(p.arrival_time for p in pool)
                gantt.append(GanttEntry("IDLE", clock, next_arr))
                clock = next_arr
                continue

            chosen = min(ready, key=lambda p: (p.burst_time, p.pid))
            start, end = clock, clock + chosen.burst_time
            chosen.record_execution(start, end)
            gantt.append(GanttEntry(chosen.pid, start, end))
            clock = end
            chosen.finalize_metrics(clock)
            pool.remove(chosen)
            completed += 1

        return gantt


class RoundRobinScheduler(Scheduler):


    def __init__(self, processes: List[Process], time_quantum: int) -> None:
        super().__init__(processes)
        if time_quantum <= 0:
            raise ValueError("time_quantum must be a positive integer.")
        self.time_quantum: int = int(time_quantum)

    @property
    def algorithm_name(self) -> str:
        return f"Round Robin (Time Quantum = {self.time_quantum})"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        not_arrived = sorted(self.processes, key=lambda p: (p.arrival_time, p.pid))
        ready: deque[Process] = deque()
        clock: float = 0.0
        completed: int = 0

        def admit(up_to: float) -> None:
            while not_arrived and not_arrived[0].arrival_time <= up_to:
                ready.append(not_arrived.pop(0))

        admit(clock)

        while completed < len(self.processes):
            if not ready:
                if not not_arrived:
                    break
                next_arr = not_arrived[0].arrival_time
                gantt.append(GanttEntry("IDLE", clock, next_arr))
                clock = next_arr
                admit(clock)
                continue

            current = ready.popleft()
            slice_len = min(self.time_quantum, current.remaining_time)
            start, end = clock, clock + slice_len
            current.record_execution(start, end)
            gantt.append(GanttEntry(current.pid, start, end))
            clock = end


            admit(clock)

            if current.is_complete:
                current.finalize_metrics(clock)
                completed += 1
            else:
                ready.append(current)

        return gantt


class PriorityScheduler(Scheduler):


    @property
    def algorithm_name(self) -> str:
        return "Priority Scheduling (Non-preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        pool: List[Process] = list(self.processes)
        clock: float = 0.0
        completed: int = 0

        while completed < len(self.processes):
            ready = [p for p in pool if p.arrival_time <= clock]
            if not ready:
                next_arr = min(p.arrival_time for p in pool)
                gantt.append(GanttEntry("IDLE", clock, next_arr))
                clock = next_arr
                continue

            chosen = min(ready, key=lambda p: (p.priority, p.pid))
            start, end = clock, clock + chosen.burst_time
            chosen.record_execution(start, end)
            gantt.append(GanttEntry(chosen.pid, start, end))
            clock = end
            chosen.finalize_metrics(clock)
            pool.remove(chosen)
            completed += 1

        return gantt


class SRTFScheduler(Scheduler):


    @property
    def algorithm_name(self) -> str:
        return "Shortest Remaining Time First (SRTF, Preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        pool: List[Process] = list(self.processes)
        clock: float = 0.0
        completed: int = 0
        current_pid: str = ""
        current_start: float = 0.0

        def commit(end: float) -> None:
            if current_pid and end > current_start:
                gantt.append(GanttEntry(current_pid, current_start, end))

        while completed < len(self.processes):
            ready = [p for p in pool if p.arrival_time <= clock and not p.is_complete]

            if not ready:
                future = [p.arrival_time for p in pool if not p.is_complete]
                if not future:
                    break
                next_arr = min(future)
                commit(clock)
                gantt.append(GanttEntry("IDLE", clock, next_arr))
                current_pid = ""
                clock = next_arr
                continue

            chosen = min(ready, key=lambda p: (p.remaining_time, p.pid))

            if chosen.pid != current_pid:
                commit(clock)
                current_pid = chosen.pid
                current_start = clock

            chosen.record_execution(clock, clock + 1)
            clock += 1

            if chosen.is_complete:
                commit(clock)
                current_pid = ""
                chosen.finalize_metrics(clock)
                pool.remove(chosen)
                completed += 1

        return gantt


_ANSI_COLOURS = ["\033[36m", "\033[33m", "\033[32m", "\033[35m", "\033[34m",
                 "\033[31m", "\033[96m", "\033[93m", "\033[92m", "\033[95m"]
_ANSI_RESET   = "\033[0m"
_ANSI_IDLE    = "\033[90m"
_ANSI_BOLD    = "\033[1m"


def _colour_for_pid(pid: str, colour_map: dict) -> str:
    if pid == "IDLE":
        return _ANSI_IDLE
    if pid not in colour_map:
        colour_map[pid] = _ANSI_COLOURS[len(colour_map) % len(_ANSI_COLOURS)]
    return colour_map[pid]


def _fmt_time(t: float) -> str:
    return str(int(t)) if t == int(t) else f"{t:.2f}"


def render_gantt_bracket(gantt: List[GanttEntry]) -> str:

    if not gantt:
        return "(empty timeline)"
    return "".join(
        f"[{e.process_id}|{_fmt_time(e.start)}-{_fmt_time(e.end)}]"
        for e in gantt
    )


def render_gantt_boxed(gantt: List[GanttEntry]) -> str:

    if not gantt:
        return "(empty timeline)"

    MIN_BOX = 4
    top = "|"
    boundaries: list = []

    for entry in gantt:
        label  = entry.process_id
        inner  = max(MIN_BOX, len(label) + 2)
        pad_l  = (inner - len(label)) // 2
        pad_r  = inner - len(label) - pad_l
        boundaries.append((len(top), entry.start))
        top += " " * pad_l + label + " " * pad_r + "|"

    boundaries.append((len(top) - 1, gantt[-1].end))

    ruler = list(" " * len(top))
    for col, t in boundaries:
        for i, ch in enumerate(_fmt_time(t)):
            pos = col + i
            if pos < len(ruler):
                ruler[pos] = ch
            else:
                ruler.append(ch)

    return top + "\n" + "".join(ruler).rstrip()


def render_gantt_coloured(gantt: List[GanttEntry]) -> str:

    if not gantt:
        return "(empty timeline)"
    colour_map: dict = {}
    parts = []
    for e in gantt:
        c = _colour_for_pid(e.process_id, colour_map)
        parts.append(
            f"{c}[{e.process_id}|{_fmt_time(e.start)}-{_fmt_time(e.end)}]{_ANSI_RESET}"
        )
    return "".join(parts)


def render_execution_slices(gantt: List[GanttEntry]) -> str:

    if not gantt:
        return "(empty timeline)"
    seen: dict = {}
    for e in gantt:
        s = f"[{_fmt_time(e.start)}-{_fmt_time(e.end)}]"
        if e.process_id not in seen:
            seen[e.process_id] = []
        seen[e.process_id].append(s)
    col_w = max(len(pid) for pid in seen)
    sep = "-" * col_w + "  " + "-" * 40
    lines = [f"{'PID':<{col_w}}  Slices", sep]
    for pid, slices in seen.items():
        lines.append(f"{pid:<{col_w}}  {'  '.join(slices)}")
    return "\n".join(lines)


WIDTH = 76


def _supports_colour() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


USE_COLOUR = _supports_colour()


def _c(text: str, code: str) -> str:
    return f"{code}{text}{_ANSI_RESET}" if USE_COLOUR else text


def banner(title: str) -> None:
    print()
    print(_c("=" * WIDTH, _ANSI_BOLD))
    print(_c(f"  {title}", _ANSI_BOLD))
    print(_c("=" * WIDTH, _ANSI_BOLD))


def section(title: str) -> None:
    print(f"\n  {'─' * (WIDTH - 2)}")
    print(f"  {_c(title, _ANSI_BOLD)}")
    print(f"  {'─' * (WIDTH - 2)}")


def ok(msg: str)   -> None: print(f"  \033[92m✓\033[0m  {msg}" if USE_COLOUR else f"  [OK]  {msg}")
def info(msg: str) -> None: print(f"  \033[96mℹ\033[0m  {msg}" if USE_COLOUR else f"  [i]  {msg}")
def warn(msg: str) -> None: print(f"  \033[93m⚠\033[0m  {msg}" if USE_COLOUR else f"  [!]  {msg}")
def err(msg: str)  -> None: print(f"  \033[91m✗\033[0m  {msg}" if USE_COLOUR else f"  [x]  {msg}")


def _prompt_int(prompt: str, min_val: int = 0, max_val: int = 10_000) -> int:
    while True:
        try:
            val = int(input(f"  {prompt}: ").strip())
            if min_val <= val <= max_val:
                return val
            err(f"Enter a value between {min_val} and {max_val}.")
        except (ValueError, EOFError):
            err("Invalid input — please enter a whole number.")


def _prompt_str(prompt: str, max_len: int = 20) -> str:
    while True:
        raw = input(f"  {prompt}: ").strip()
        if 1 <= len(raw) <= max_len:
            return raw
        err(f"Please enter 1–{max_len} characters.")


def input_processes_manually() -> List[Process]:

    section("Manual Process Entry")
    n = _prompt_int("Number of processes (1–20)", min_val=1, max_val=20)
    processes: List[Process] = []
    existing_pids: set = set()

    for i in range(1, n + 1):
        print(f"\n  — Process {i} of {n} —")
        while True:
            default_pid = f"P{i}"
            raw = input(f"  PID (default {default_pid}): ").strip()
            pid = raw if raw else default_pid
            if pid in existing_pids:
                warn(f"'{pid}' already used. Choose a different ID.")
            else:
                existing_pids.add(pid)
                break
        at  = _prompt_int("Arrival Time (≥ 0)", min_val=0, max_val=9_999)
        bt  = _prompt_int("Burst  Time (≥ 1)", min_val=1, max_val=9_999)
        pri = _prompt_int("Priority   (lower # = higher priority, default 0)",
                          min_val=0, max_val=100)
        processes.append(Process(pid=pid, arrival_time=at, burst_time=bt, priority=pri))
        ok(f"{pid}  AT={at}  BT={bt}  Priority={pri}")

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

        processes.append(Process(
            pid=pid,
            arrival_time=random.randint(0, max_at),
            burst_time=random.randint(min_bt, max_bt),
            priority=random.randint(min_pri, max_pri),
        ))
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


def select_algorithms(processes: List[Process]) -> Tuple[List[Scheduler], Optional[int]]:

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
    if choice in (3, 6):
        quantum = _prompt_int("\n  Round Robin — Time Quantum (≥ 1)", min_val=1, max_val=9_999)

    schedulers: List[Scheduler] = []
    if choice in (1, 6): schedulers.append(FCFSScheduler(list(processes)))
    if choice in (2, 6): schedulers.append(SJFScheduler(list(processes)))
    if choice in (3, 6): schedulers.append(RoundRobinScheduler(list(processes), quantum))
    if choice in (4, 6): schedulers.append(PriorityScheduler(list(processes)))
    if choice in (5, 6): schedulers.append(SRTFScheduler(list(processes)))

    return schedulers, quantum


def print_process_table(processes: List[Process]) -> None:
    col = max(5, max(len(p.pid) for p in processes))
    print(f"  {'PID':<{col}}  {'Arrival':>7}  {'Burst':>5}  {'Priority':>8}")
    print("  " + "-" * (col + 28))
    for p in processes:
        print(f"  {p.pid:<{col}}  {int(p.arrival_time):>7}  "
              f"{int(p.burst_time):>5}  {p.priority:>8}")
    print()


def print_result(result: SchedulingResult, show_slices: bool = False) -> None:
    banner(f"Algorithm: {result.algorithm_name}")

    print(f"\n  Gantt Chart (bracket):")
    print(f"  {render_gantt_bracket(result.gantt_chart)}")

    if USE_COLOUR:
        print(f"\n  Gantt Chart (coloured):")
        print(f"  {render_gantt_coloured(result.gantt_chart)}")

    print(f"\n  Gantt Chart (boxed):")
    for line in render_gantt_boxed(result.gantt_chart).splitlines():
        print(f"  {line}")

    if show_slices:
        print(f"\n  Execution Slices per Process:")
        for line in render_execution_slices(result.gantt_chart).splitlines():
            print(f"  {line}")

    print(f"\n  Process Metrics:")
    for line in result.summary_table().splitlines():
        print(f"  {line}")
    print()


def print_comparison(results: List[SchedulingResult]) -> None:
    banner("Performance Comparison Summary")
    col = max(max(len(r.algorithm_name) for r in results), 45)
    header = f"  {'Algorithm':<{col}}  {'Avg WT':>8}  {'Avg TAT':>9}"
    sep    = "  " + "-" * (col + 22)
    print(header)
    print(sep)
    for r in results:
        print(f"  {r.algorithm_name:<{col}}  "
              f"{r.average_waiting_time:>8.2f}  "
              f"{r.average_turnaround_time:>9.2f}")
    print(sep)
    best_wt  = min(results, key=lambda r: r.average_waiting_time)
    best_tat = min(results, key=lambda r: r.average_turnaround_time)
    ok(f"Lowest Avg WT  : {best_wt.algorithm_name}  ({best_wt.average_waiting_time:.2f})")
    ok(f"Lowest Avg TAT : {best_tat.algorithm_name}  ({best_tat.average_turnaround_time:.2f})")
    print()


def offer_csv_export(results: List[SchedulingResult]) -> None:
    section("Export Results to CSV")
    raw = input("  Export results to CSV files? (y/N): ").strip().lower()
    if raw not in ("y", "yes"):
        info("Export skipped.")
        return
    export_dir = input("  Export directory (default: current folder): ").strip() or "."
    os.makedirs(export_dir, exist_ok=True)
    for result in results:
        safe = (result.algorithm_name
                .replace(" ", "_").replace(",", "")
                .replace("(", "").replace(")", "")
                .replace("=", ""))
        path = os.path.join(export_dir, f"{safe}.csv")
        result.export_csv(path)
        ok(f"Saved: {path}")


def main() -> None:
    banner("CPU Scheduling Simulator")
    print("""
  Algorithms  : FCFS · SJF · Round Robin · Priority · SRTF (Advanced)
  Formulas    : TAT = CT − AT     |     WT = TAT − BT
  Features    : Interactive input · Random workload · CSV export
""")


    section("Process Input Method")
    print("""
    1.  Enter processes manually
    2.  Generate random workload  [Advanced Feature]
    3.  Use built-in demo dataset
    """)
    inp = _prompt_int("Select option (1–3)", min_val=1, max_val=3)

    if inp == 1:
        processes = input_processes_manually()
    elif inp == 2:
        processes = generate_random_processes()
    else:
        processes = use_demo_processes()
        info("Built-in demo dataset loaded.")

    section("Process List")
    print_process_table(processes)


    schedulers, _ = select_algorithms(processes)

    show_slices = input(
        "\n  Show per-slice execution detail? (y/N): "
    ).strip().lower() in ("y", "yes")


    results: List[SchedulingResult] = []
    for sched in schedulers:
        try:
            result = sched.run()
            results.append(result)
            print_result(result, show_slices=show_slices)
        except Exception as exc:
            err(f"Failed to run {sched.algorithm_name}: {exc}")


    if len(results) > 1:
        print_comparison(results)


    if results:
        offer_csv_export(results)

    banner("Simulation Complete")


class _TestFCFS(unittest.TestCase):
    def _run(self):
        procs = [Process("P1",0,5,2), Process("P2",0,3,1),
                 Process("P3",2,8,4), Process("P4",4,6,3), Process("P5",6,2,5)]
        return FCFSScheduler(procs).run()

    def test_order(self):
        r = self._run()
        self.assertEqual([e.process_id for e in r.gantt_chart], ["P1","P2","P3","P4","P5"])

    def test_averages(self):
        r = self._run()
        self.assertAlmostEqual(r.average_waiting_time, 7.80, places=2)
        self.assertAlmostEqual(r.average_turnaround_time, 12.60, places=2)

    def test_formulas(self):
        for p in self._run().processes:
            self.assertEqual(p.turnaround_time, p.completion_time - p.arrival_time)
            self.assertEqual(p.waiting_time, p.turnaround_time - p.burst_time)


class _TestSJF(unittest.TestCase):
    def test_order_and_averages(self):
        procs = [Process("P1",0,5), Process("P2",0,3), Process("P3",2,8),
                 Process("P4",4,6), Process("P5",6,2)]
        r = SJFScheduler(procs).run()
        self.assertEqual([e.process_id for e in r.gantt_chart], ["P2","P1","P5","P4","P3"])
        self.assertAlmostEqual(r.average_waiting_time, 5.00, places=2)


class _TestRR(unittest.TestCase):
    def test_averages(self):
        procs = [Process("P1",0,5), Process("P2",0,3), Process("P3",2,8),
                 Process("P4",4,6), Process("P5",6,2)]
        r = RoundRobinScheduler(procs, time_quantum=4).run()
        self.assertAlmostEqual(r.average_waiting_time, 10.20, places=2)

    def test_large_quantum_eq_fcfs(self):
        p_rr   = [Process("P1",0,3), Process("P2",1,4), Process("P3",2,2)]
        p_fcfs = [Process("P1",0,3), Process("P2",1,4), Process("P3",2,2)]
        rr_m   = [(p.pid, p.waiting_time) for p in RoundRobinScheduler(p_rr, 999).run().processes]
        fc_m   = [(p.pid, p.waiting_time) for p in FCFSScheduler(p_fcfs).run().processes]
        self.assertEqual(rr_m, fc_m)


class _TestEdgeCases(unittest.TestCase):
    def test_idle_gap(self):
        r = FCFSScheduler([Process("P1",5,3)]).run()
        self.assertEqual(r.gantt_chart[0].process_id, "IDLE")

    def test_empty_list_raises(self):
        with self.assertRaises(ValueError):
            FCFSScheduler([])

    def test_negative_arrival_raises(self):
        with self.assertRaises(ValueError):
            Process("P1", -1, 5)

    def test_zero_burst_raises(self):
        with self.assertRaises(ValueError):
            Process("P1", 0, 0)

    def test_negative_priority_raises(self):
        with self.assertRaises(ValueError):
            Process("P1", 0, 5, priority=-1)

    def test_duplicate_pid_raises(self):
        with self.assertRaises(ValueError):
            FCFSScheduler([Process("P1", 0, 5), Process("P1", 2, 3)])


def run_tests() -> None:

    info("Running built-in self-check (FCFS/SJF/RR/edge cases) before startup...")
    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()
    for cls in (_TestFCFS, _TestSJF, _TestRR, _TestEdgeCases):
        suite.addTests(loader.loadTestsFromTestCase(cls))
    runner = unittest.TextTestRunner(verbosity=0, stream=open(os.devnull, "w"))
    result = runner.run(suite)
    total  = result.testsRun
    fails  = len(result.failures) + len(result.errors)
    if fails == 0:
        ok(f"All {total} self-tests passed.")
    else:
        warn(f"{fails}/{total} self-tests FAILED.  Run with --test for details.")


if __name__ == "__main__":
    if "--test" in sys.argv:

        sys.argv = [sys.argv[0]]
        unittest.main(
            defaultTest=None,
            testLoader=unittest.TestLoader(),
            testRunner=unittest.TextTestRunner(verbosity=2),
            module=__name__,
            exit=True,
        )
    else:
        run_tests()
        main()

