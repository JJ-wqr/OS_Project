#HANINA ELIAS ABDOSH - 2802516030
#JEREMY NATHANAEL GUNAWAN - 2802522960
from __future__ import annotations

import copy
import csv
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GanttEntry:
    # start of class GanttEntry
    # Represents a single scheduled execution slice in the Gantt chart.
    # process_id: PID of the process that ran.
    # start/end : time boundaries of the slice.
    # end of class GanttEntry

    process_id: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        # start of function duration
        # Returns how long the slice lasted.
        # end of function duration
        return self.end - self.start


@dataclass
class Process:
    # start of class Process
    # Holds per-process input (pid/arrival/burst/priority) and simulation state.
    # end of class Process

    pid: str
    arrival_time: float
    burst_time: float
    priority: int = 0

    # These fields are populated/reset by the scheduler simulation.
    remaining_time: float = field(init=False, default=0.0)
    completion_time: Optional[float] = field(init=False, default=None)
    waiting_time: Optional[float] = field(init=False, default=None)
    turnaround_time: Optional[float] = field(init=False, default=None)
    response_time: Optional[float] = field(init=False, default=None)
    execution_history: List[GanttEntry] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        # start of function __post_init__
        # Validates input types and ranges early.
        # end of function __post_init__

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

        # Initialise remaining_time based on burst_time.
        self.remaining_time = float(self.burst_time)

    def reset_for_simulation(self) -> None:
        # start of function reset_for_simulation
        # Clears per-run state so the same Process objects can be reused for
        # different scheduling algorithms.
        # end of function reset_for_simulation

        self.remaining_time = float(self.burst_time)
        self.completion_time = None
        self.waiting_time = None
        self.turnaround_time = None
        self.response_time = None
        self.execution_history = []

    def record_execution(self, start: float, end: float) -> None:
        # start of function record_execution
        # Records that this process executed during [start, end).
        # Updates response time on first execution, and reduces remaining_time.
        # end of function record_execution

        if end <= start:
            raise ValueError(
                f"[{self.pid}] Invalid execution slice: start={start}, end={end}."
            )

        # Response time is defined as the time from arrival to first CPU use.
        if self.response_time is None:
            self.response_time = start - self.arrival_time

        self.execution_history.append(GanttEntry(self.pid, start, end))
        self.remaining_time -= (end - start)

        # Hard guard: remaining time should not go negative except for tiny
        # floating-point noise.
        if self.remaining_time < -1e-9:
            raise RuntimeError(
                f"[{self.pid}] remaining_time went negative ({self.remaining_time:.6f}). "
                f"This is a scheduler bug."
            )

        # Snap to exactly 0 when close.
        if abs(self.remaining_time) < 1e-9:
            self.remaining_time = 0.0

    @property
    def is_complete(self) -> bool:
        # start of function is_complete
        # Convenience boolean: has the process finished (remaining_time == 0)?
        # end of function is_complete

        return self.remaining_time == 0.0

    def finalize_metrics(self, completion_time: float) -> None:
        # start of function finalize_metrics
        # Computes final completion/turnaround/waiting metrics using completion_time.
        # end of function finalize_metrics

        self.completion_time = completion_time
        self.turnaround_time = self.completion_time - self.arrival_time
        self.waiting_time = self.turnaround_time - self.burst_time

        # Waiting time should not be negative; if it is, the scheduler logic is wrong.
        if self.waiting_time < -1e-9:
            raise RuntimeError(
                f"[{self.pid}] Negative waiting time ({self.waiting_time:.6f}). "
                f"Check scheduler logic."
            )

    def __repr__(self) -> str:
        # start of function __repr__
        # Developer-friendly representation for debugging.
        # end of function __repr__
        return (
            f"Process(pid={self.pid!r}, AT={self.arrival_time}, "
            f"BT={self.burst_time}, priority={self.priority}, "
            f"remaining={self.remaining_time}, CT={self.completion_time})"
        )


@dataclass
class SchedulingResult:
    # start of class SchedulingResult
    # Bundles the output of one scheduling algorithm run.
    # end of class SchedulingResult

    algorithm_name: str
    processes: List[Process]
    gantt_chart: List[GanttEntry]
    average_waiting_time: float
    average_turnaround_time: float

    def summary_table(self) -> str:
        # start of function summary_table
        # Builds a formatted string table of per-process metrics.
        # end of function summary_table

        if not self.processes:
            return "(no processes)"

        col_pid = max(5, max(len(p.pid) for p in self.processes))
        cols = [col_pid, 6, 6, 10, 6, 6, 6, 13]
        headers = ["PID", "AT", "BT", "Priority", "CT", "TAT", "WT", "Response"]

        def row(*values) -> str:
            # Helper that left-justifies each column to a fixed width.
            return "  ".join(str(v).ljust(w) for v, w in zip(values, cols))

        def fmt(x: Optional[float]) -> str:
            # Helper that prints floats compactly, or "?" when None.
            if x is None:
                return "?"
            return str(int(x)) if x == int(x) else f"{x:.2f}"

        sep = "-" * (sum(cols) + 2 * (len(cols) - 1))
        lines = [row(*headers), sep]
        for p in self.processes:
            lines.append(
                row(
                    p.pid,
                    fmt(p.arrival_time),
                    fmt(p.burst_time),
                    p.priority,
                    fmt(p.completion_time),
                    fmt(p.turnaround_time),
                    fmt(p.waiting_time),
                    fmt(p.response_time),
                )
            )
        lines.append(sep)
        lines.append(f"  Average Waiting Time    : {self.average_waiting_time:.2f}")
        lines.append(f"  Average Turnaround Time : {self.average_turnaround_time:.2f}")
        return "\n".join(lines)

    def export_csv(self, filepath: str) -> None:
        # start of function export_csv
        # Writes results to a CSV file.
        # end of function export_csv

        fieldnames = [
            "PID",
            "ArrivalTime",
            "BurstTime",
            "Priority",
            "CompletionTime",
            "TurnaroundTime",
            "WaitingTime",
            "ResponseTime",
        ]
        with open(filepath, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for p in self.processes:
                writer.writerow(
                    {
                        "PID": p.pid,
                        "ArrivalTime": p.arrival_time,
                        "BurstTime": p.burst_time,
                        "Priority": p.priority,
                        "CompletionTime": p.completion_time,
                        "TurnaroundTime": p.turnaround_time,
                        "WaitingTime": p.waiting_time,
                        "ResponseTime": p.response_time,
                    }
                )


class Scheduler(ABC):
    # start of class Scheduler
    # Base class shared by all scheduling algorithms.
    # It deep-copies processes, resets per-run state, calls _execute(), and
    # then aggregates per-process metrics into SchedulingResult.
    # end of class Scheduler

    def __init__(self, processes: List[Process]) -> None:
        # start of function __init__
        # Ensures unique PIDs and deep-copies processes so each scheduler run
        # does not mutate the original objects.
        # end of function __init__

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

        self.processes: List[Process] = [copy.deepcopy(p) for p in processes]

    @property
    @abstractmethod
    def algorithm_name(self) -> str:
        # start of function algorithm_name
        # Each concrete scheduler must provide a human-readable algorithm name.
        # end of function algorithm_name

        ...

    @abstractmethod
    def _execute(self) -> List[GanttEntry]:
        # start of function _execute
        # Each concrete scheduler implements its scheduling simulation here.
        # Must return the final list of Gantt slices and set each process's
        # completion_time (and optionally other metrics via record_execution).
        # end of function _execute

        ...

    def run(self) -> SchedulingResult:
        # start of function run
        # Main execution wrapper:
        # 1) Reset processes
        # 2) Call the algorithm-specific _execute()
        # 3) Validate all processes were finalized
        # 4) Compute averages and return a SchedulingResult
        # end of function run

        for p in self.processes:
            p.reset_for_simulation()

        gantt = self._execute()

        # Validate: schedulers should have finalized completion_time.
        unfinished = [p for p in self.processes if p.completion_time is None]
        if unfinished:
            names = ", ".join(p.pid for p in unfinished)
            raise RuntimeError(
                f"{self.algorithm_name}: processes were never finalised: {names}."
            )

        n = len(self.processes)
        return SchedulingResult(
            algorithm_name=self.algorithm_name,
            processes=list(self.processes),
            gantt_chart=gantt,
            average_waiting_time=sum(p.waiting_time for p in self.processes) / n,
            average_turnaround_time=sum(p.turnaround_time for p in self.processes) / n,
        )

