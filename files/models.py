

from __future__ import annotations

import csv
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


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
            raise ValueError(
                f"[{self.pid}] Invalid execution slice: start={start}, end={end}."
            )

        if self.response_time is None:
            self.response_time = start - self.arrival_time
        self.execution_history.append(GanttEntry(self.pid, start, end))
        self.remaining_time -= (end - start)
        if self.remaining_time < -1e-9:
            raise RuntimeError(
                f"[{self.pid}] remaining_time went negative ({self.remaining_time:.6f}). "
                f"This is a scheduler bug."
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


        col_pid  = max(5, max(len(p.pid) for p in self.processes))
        cols = [col_pid, 6, 6, 10, 6, 6, 6, 13]
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
                p.pid,
                fmt(p.arrival_time),
                fmt(p.burst_time),
                p.priority,
                fmt(p.completion_time),
                fmt(p.turnaround_time),
                fmt(p.waiting_time),
                fmt(p.response_time),
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

