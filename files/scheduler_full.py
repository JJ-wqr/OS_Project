#!/usr/bin/env python3
"""
CPU Scheduling Simulator (Student-ready single-file implementation)

Name: __________________
Student ID: __________________

Implements:
 - First Come First Serve (FCFS)
 - Shortest Job First (SJF) - Non-preemptive
 - Round Robin (RR)
 - Priority Scheduling - Non-preemptive

Features:
 - Dataclasses, type hints, docstrings, inline comments.
 - Handles edge cases: empty process list, zero burst_time (instant completion),
   simultaneous arrivals, duplicate PIDs (warn), floating point times.
 - Text-based Gantt chart (bracket style) and boxed style (boxed scales by label).
 - Canonical formulas explicitly applied:
       Turnaround Time (TAT) = Completion Time (CT) - Arrival Time (AT)
       Waiting Time   (WT)  = Turnaround Time (TAT) - Burst Time (BT)
 - Polished console output for screenshots and demos.

Run:
    python3 scheduler_full.py
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Deque
from collections import deque
import math
import sys
import warnings

# ---------------------------
# Data models
# ---------------------------

@dataclass
class GanttEntry:
    process_id: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start

    def formatted(self) -> str:
        # Format times compactly: if integer, show as int; else 2 decimals
        def fmt(t: float) -> str:
            return str(int(t)) if math.isclose(t, round(t)) else f"{t:.2f}"
        return f"[{self.process_id}|{fmt(self.start)}-{fmt(self.end)}]"

@dataclass
class Process:
    pid: str
    arrival_time: float
    burst_time: float
    priority: int = 0

    # Mutable simulation state (reset for each run)
    remaining_time: float = field(init=False, default=0.0)
    completion_time: Optional[float] = field(init=False, default=None)
    waiting_time: Optional[float] = field(init=False, default=None)
    turnaround_time: Optional[float] = field(init=False, default=None)
    response_time: Optional[float] = field(init=False, default=None)
    execution_history: List[GanttEntry] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        # Input validation: arrival_time >= 0 and burst_time >= 0.
        if not isinstance(self.arrival_time, (int, float)):
            raise TypeError(f"{self.pid}: arrival_time must be numeric.")
        if not isinstance(self.burst_time, (int, float)):
            raise TypeError(f"{self.pid}: burst_time must be numeric.")
        if self.arrival_time < 0:
            raise ValueError(f"{self.pid}: arrival_time cannot be negative.")
        if self.burst_time < 0:
            raise ValueError(f"{self.pid}: burst_time cannot be negative.")
        # Initialize remaining_time to the original burst.
        self.remaining_time = float(self.burst_time)

    def reset_for_simulation(self) -> None:
        self.remaining_time = float(self.burst_time)
        self.completion_time = None
        self.waiting_time = None
        self.turnaround_time = None
        self.response_time = None
        self.execution_history = []

    def record_execution(self, start: float, end: float) -> None:
        if end < start:
            raise ValueError(f"{self.pid}: invalid execution slice ({start} -> {end})")
        # Set response_time on first dispatch
        if self.response_time is None:
            # Response time = first_start - arrival_time
            self.response_time = start - self.arrival_time
        # Only record non-zero-duration slices
        if end > start:
            self.execution_history.append(GanttEntry(self.pid, start, end))
            self.remaining_time -= (end - start)
            # Defensive clamp
            if self.remaining_time < -1e-9:
                raise RuntimeError(f"{self.pid}: remaining_time went negative ({self.remaining_time}).")
            # Clamp tiny floating negative to zero
            if abs(self.remaining_time) < 1e-9:
                self.remaining_time = 0.0

    @property
    def is_complete(self) -> bool:
        return math.isclose(self.remaining_time, 0.0)

    def finalize_metrics(self, completion_time: float) -> None:
        # Store completion time
        self.completion_time = completion_time
        # Turnaround Time (TAT) = Completion Time (CT) - Arrival Time (AT)
        self.turnaround_time = self.completion_time - self.arrival_time
        # Waiting Time (WT) = Turnaround Time (TAT) - Burst Time (BT)
        self.waiting_time = self.turnaround_time - self.burst_time
        # Allow zero WT, but not negative (negative indicates a scheduler bug)
        if self.waiting_time < -1e-9:
            raise RuntimeError(f"{self.pid}: computed negative waiting time ({self.waiting_time}).")

    def __repr__(self) -> str:
        return f"Process(pid={self.pid}, AT={self.arrival_time}, BT={self.burst_time}, prio={self.priority})"


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
        header = f"{'PID':<6}{'AT':<8}{'BT':<8}{'CT':<8}{'TAT':<8}{'WT':<8}"
        lines = [header, "-" * len(header)]
        for p in self.processes:
            def fmt(x: Optional[float]) -> str:
                if x is None:
                    return "?"
                return str(int(x)) if math.isclose(x, round(x)) else f"{x:.2f}"
            lines.append(
                f"{p.pid:<6}{fmt(p.arrival_time):<8}{fmt(p.burst_time):<8}"
                f"{fmt(p.completion_time):<8}{fmt(p.turnaround_time):<8}{fmt(p.waiting_time):<8}"
            )
        lines.append("-" * len(header))
        lines.append(f"Average Waiting Time:    {self.average_waiting_time:.2f}")
        lines.append(f"Average Turnaround Time: {self.average_turnaround_time:.2f}")
        return "\n".join(lines)


# ---------------------------
# Scheduler base class
# ---------------------------

class Scheduler:
    def __init__(self, processes: List[Process]) -> None:
        # Allow empty lists; run() will return an empty result rather than raising.
        self.processes = processes

    @property
    def algorithm_name(self) -> str:
        raise NotImplementedError

    def _validate_inputs(self) -> None:
        # Basic validation: numeric non-negative times already in Process, but
        # check duplicate PIDs and non-numeric priorities.
        pids = [p.pid for p in self.processes]
        dupes = {pid for pid in pids if pids.count(pid) > 1}
        if dupes:
            # Warn but do not forcibly reject — duplicates can be allowed but are confusing.
            warnings.warn(f"Duplicate PIDs detected: {sorted(list(dupes))}. This may confuse outputs.")
        for p in self.processes:
            if not isinstance(p.priority, int):
                raise TypeError(f"{p.pid}: priority must be an integer.")

    def _execute(self) -> List[GanttEntry]:
        raise NotImplementedError

    def run(self) -> SchedulingResult:
        # Reset processes to initial simulation state
        for p in self.processes:
            p.reset_for_simulation()

        # Validate inputs
        self._validate_inputs()

        # If there are no processes, return an empty result (graceful)
        if not self.processes:
            return SchedulingResult(
                algorithm_name=self.algorithm_name,
                processes=[],
                gantt_chart=[],
                average_waiting_time=0.0,
                average_turnaround_time=0.0,
            )

        # Pre-handle processes with burst_time == 0: they "complete" at arrival
        zero_burst = [p for p in self.processes if math.isclose(p.burst_time, 0.0)]
        # These will be finalized at arrival_time as soon as the clock reaches the arrival.
        # To simplify downstream algorithm logic, we leave them in the process list but
        # our algorithms must be written to skip processes with remaining_time == 0 when dispatching.

        gantt = self._execute()

        # Defensive: every process must be finalized (completion_time set).
        unfinished = [p for p in self.processes if p.completion_time is None]
        if unfinished:
            names = ", ".join(p.pid for p in unfinished)
            raise RuntimeError(f"{self.algorithm_name}: unfinished processes: {names}")

        total_wt = sum(p.waiting_time for p in self.processes)
        total_tat = sum(p.turnaround_time for p in self.processes)
        n = len(self.processes)

        return SchedulingResult(
            algorithm_name=self.algorithm_name,
            processes=list(self.processes),
            gantt_chart=gantt,
            average_waiting_time=(total_wt / n) if n else 0.0,
            average_turnaround_time=(total_tat / n) if n else 0.0,
        )

# ---------------------------
# Helper formatting functions
# ---------------------------

def render_gantt_chart(gantt_chart: List[GanttEntry]) -> str:
    if not gantt_chart:
        return "(empty timeline)"
    return "".join(entry.formatted() for entry in gantt_chart)

def render_gantt_chart_boxed(gantt_chart: List[GanttEntry]) -> str:
    # Simpler boxed view: each entry is rendered as a label with separators.
    if not gantt_chart:
        return "(empty timeline)"
    top = "|"
    bottom = ""
    cursor = 0
    boxes = []
    for e in gantt_chart:
        label = e.process_id
        box = f" {label} "
        boxes.append(box)
    top += "|".join(boxes) + "|"
    # bottom shows boundaries (start times and final end)
    times = []
    for e in gantt_chart:
        times.append(e.start)
    times.append(gantt_chart[-1].end)
    # format times under boxes approximately (not perfectly proportional)
    bottom = " ".join(str(int(t) if math.isclose(t, round(t)) else f"{t:.2f}") for t in times)
    return top + "\n" + bottom

# ---------------------------
# Algorithm implementations
# ---------------------------

class FCFSScheduler(Scheduler):
    @property
    def algorithm_name(self) -> str:
        return "First Come First Serve (FCFS)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        # Sort by arrival_time then PID
        ordered = sorted(self.processes, key=lambda p: (p.arrival_time, p.pid))
        clock = 0.0
        for p in ordered:
            # If p already completed because burst_time == 0 and we finalized earlier
            if p.is_complete:
                # We must finalize at the arrival_time if not already done
                if p.completion_time is None:
                    # It "finishes" at its arrival
                    p.finalize_metrics(completion_time=p.arrival_time)
                continue
            # If CPU idle until p.arrival_time, record IDLE
            if clock < p.arrival_time:
                gantt.append(GanttEntry("IDLE", clock, p.arrival_time))
                clock = p.arrival_time
            start = clock
            end = clock + p.remaining_time  # remaining_time equals burst_time for non-preemptive
            p.record_execution(start, end)
            if end > start:
                gantt.append(GanttEntry(p.pid, start, end))
            clock = end
            p.finalize_metrics(completion_time=clock)
        return gantt

class SJFScheduler(Scheduler):
    @property
    def algorithm_name(self) -> str:
        return "Shortest Job First (SJF, Non-preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        # Work on a copy of the processes for selection; still finalize on original objects
        remaining_pool = [p for p in self.processes if not p.is_complete]
        # We will still consider processes with burst_time == 0 handled earlier (they are is_complete)
        clock = 0.0
        completed = 0
        total = len(self.processes)
        while any(not p.is_complete for p in self.processes):
            ready = [p for p in remaining_pool if (p.arrival_time <= clock and not p.is_complete)]
            if not ready:
                # If there's some process not arrived yet, jump to next arrival
                future = [p.arrival_time for p in remaining_pool if not p.is_complete]
                if not future:
                    break
                next_arrival = min(future)
                if clock < next_arrival:
                    gantt.append(GanttEntry("IDLE", clock, next_arrival))
                    clock = next_arrival
                continue
            # pick shortest burst (use remaining_time in case pre-handled)
            next_p = min(ready, key=lambda p: (p.remaining_time, p.pid))
            # dispatch non-preemptively
            start = clock
            end = clock + next_p.remaining_time
            next_p.record_execution(start, end)
            if end > start:
                gantt.append(GanttEntry(next_p.pid, start, end))
            clock = end
            next_p.finalize_metrics(completion_time=clock)
            # remove from remaining_pool any completed processes
            remaining_pool = [p for p in remaining_pool if not p.is_complete]
        # Finalize any zero-burst that might not have been finalized earlier (safety)
        for p in self.processes:
            if p.completion_time is None and p.is_complete:
                p.finalize_metrics(completion_time=max(p.arrival_time, clock))
        return gantt

class RoundRobinScheduler(Scheduler):
    def __init__(self, processes: List[Process], time_quantum: float):
        super().__init__(processes)
        if time_quantum <= 0:
            raise ValueError("time_quantum must be positive.")
        self.time_quantum = float(time_quantum)

    @property
    def algorithm_name(self) -> str:
        return f"Round Robin (Time Quantum = {self.time_quantum})"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        # not_arrived sorted by (arrival_time, pid)
        not_arrived = sorted(self.processes, key=lambda p: (p.arrival_time, p.pid))
        ready: Deque[Process] = deque()
        clock = 0.0
        idx_not_arrived = 0
        n = len(self.processes)

        def admit_new_arrivals(up_to_time: float) -> None:
            nonlocal idx_not_arrived
            while idx_not_arrived < len(not_arrived) and not_arrived[idx_not_arrived].arrival_time <= up_to_time:
                p = not_arrived[idx_not_arrived]
                # If p has zero burst, finalize it immediately at its arrival
                if p.is_complete:
                    if p.completion_time is None:
                        p.finalize_metrics(completion_time=p.arrival_time)
                else:
                    ready.append(p)
                idx_not_arrived += 1

        # initial admission at t=0
        admit_new_arrivals(clock)

        # Main loop
        while True:
            # If everyone finalized, break
            if all(p.is_complete for p in self.processes):
                break

            if not ready:
                # No ready processes — if there are future arrivals, idle until next arrival
                if idx_not_arrived < len(not_arrived):
                    next_arrival = not_arrived[idx_not_arrived].arrival_time
                    if clock < next_arrival:
                        gantt.append(GanttEntry("IDLE", clock, next_arrival))
                        clock = next_arrival
                    admit_new_arrivals(clock)
                    continue
                else:
                    # No pending arrivals and no ready processes (shouldn't happen)
                    break

            current = ready.popleft()
            # If somehow it was finalized elsewhere, skip
            if current.is_complete:
                if current.completion_time is None:
                    current.finalize_metrics(completion_time=max(current.arrival_time, clock))
                continue

            slice_len = min(self.time_quantum, current.remaining_time)
            start = clock
            end = clock + slice_len
            current.record_execution(start, end)
            if end > start:
                gantt.append(GanttEntry(current.pid, start, end))
            clock = end
            # admit arrivals that arrived during this slice before re-queueing
            admit_new_arrivals(clock)
            if current.is_complete:
                current.finalize_metrics(completion_time=clock)
            else:
                ready.append(current)

        # Finalize any leftover zero-burst processes if needed
        for p in self.processes:
            if p.completion_time is None and p.is_complete:
                p.finalize_metrics(completion_time=max(p.arrival_time, clock))
        return gantt

class PriorityScheduler(Scheduler):
    @property
    def algorithm_name(self) -> str:
        return "Priority Scheduling (Non-preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        remaining = [p for p in self.processes if not p.is_complete]
        clock = 0.0
        while any(not p.is_complete for p in self.processes):
            ready = [p for p in remaining if (p.arrival_time <= clock and not p.is_complete)]
            if not ready:
                future = [p.arrival_time for p in remaining if not p.is_complete]
                if not future:
                    break
                next_arrival = min(future)
                if clock < next_arrival:
                    gantt.append(GanttEntry("IDLE", clock, next_arrival))
                    clock = next_arrival
                continue
            # Lower priority number = higher priority. Tie-break on PID.
            next_p = min(ready, key=lambda p: (p.priority, p.pid))
            start = clock
            end = clock + next_p.remaining_time
            next_p.record_execution(start, end)
            if end > start:
                gantt.append(GanttEntry(next_p.pid, start, end))
            clock = end
            next_p.finalize_metrics(completion_time=clock)
            remaining = [p for p in remaining if not p.is_complete]
        for p in self.processes:
            if p.completion_time is None and p.is_complete:
                p.finalize_metrics(completion_time=max(p.arrival_time, clock))
        return gantt

# ---------------------------
# Demo main driver
# ---------------------------

def build_sample_processes() -> List[Process]:
    return [
        Process(pid="P1", arrival_time=0, burst_time=5, priority=2),
        Process(pid="P2", arrival_time=0, burst_time=3, priority=1),
        Process(pid="P3", arrival_time=2, burst_time=8, priority=4),
        Process(pid="P4", arrival_time=4, burst_time=6, priority=3),
        Process(pid="P5", arrival_time=6, burst_time=2, priority=5),
    ]

def print_result(result: SchedulingResult) -> None:
    width = 76
    print("=" * width)
    print(f"Algorithm: {result.algorithm_name}")
    print("=" * width)
    print("\nGantt Chart (bracket form):")
    print(render_gantt_chart(result.gantt_chart))
    print("\nGantt Chart (boxed form):")
    print(render_gantt_chart_boxed(result.gantt_chart))
    print("\nProcess Metrics:")
    print(result.summary_table())
    print()

def main_demo() -> None:
    print("CPU SCHEDULING SIMULATOR (DEMO)\n")
    sample = build_sample_processes()
    print(f"{'PID':<6}{'AT':<6}{'BT':<6}{'Priority':<10}")
    for p in sample:
        print(f"{p.pid:<6}{int(p.arrival_time):<6}{int(p.burst_time):<6}{p.priority:<10}")
    print()

    schedulers = [
        FCFSScheduler(sample),
        SJFScheduler(sample),
        RoundRobinScheduler(sample, time_quantum=4),
        PriorityScheduler(sample),
    ]

    results = []
    for sched in schedulers:
        result = sched.run()
        results.append(result)
        print_result(result)

    print("=" * 76)
    print("PERFORMANCE COMPARISON SUMMARY")
    print("=" * 76)
    print(f"{'Algorithm':<45}{'Avg WT':<12}{'Avg TAT':<12}")
    for res in results:
        print(f"{res.algorithm_name:<45}{res.average_waiting_time:<12.2f}{res.average_turnaround_time:<12.2f}")

# If run as script, execute demo
if __name__ == "__main__":
    main_demo()