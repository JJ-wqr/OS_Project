"""
models.py
=========
Phase 1: Object-Oriented Architecture & Data Structures.

This module defines the two foundational building blocks of the simulator:

1. Process       - a data object representing a single process and everything
                    we need to track about it (inputs, computed metrics, and
                    its execution history for the Gantt chart).

2. Scheduler      - an abstract base class (ABC) that every concrete
                    scheduling algorithm (FCFS, SJF, Round Robin, Priority)
                    must extend. It defines the *contract* that all
                    algorithms share, and centralizes logic that is common
                    to every algorithm (metric calculation, result
                    formatting) so that subclasses only need to implement
                    the part that actually differs between algorithms: the
                    order in which processes are dispatched to the CPU.

Design rationale
-----------------
We use the abstract base class / template method pattern here deliberately:

    - `run()` is the single public entry point. Every scheduler is called
      the same way: `scheduler.run()`. This is what will let us later
      swap in a Tkinter GUI or Matplotlib chart without rewriting any
      algorithm code -- the GUI only ever needs to know about `run()` and
      the resulting `GanttEntry` list / `Process` list.

    - `_execute()` is the abstract method each subclass must implement.
      It is the *only* place where FCFS, SJF, Round Robin, and Priority
      actually differ: the decision of which process to run next, and
      for how long.

    - Waiting Time and Turnaround Time are calculated in ONE place
      (`_finalize_metrics`) using the canonical formulas, so we never
      risk subtly different (and wrong) arithmetic in each algorithm:

          Turnaround Time (TAT) = Completion Time (CT) - Arrival Time (AT)
          Waiting Time   (WT)  = Turnaround Time (TAT) - Burst Time (BT)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional


# ---------------------------------------------------------------------------
# Gantt chart support structure
# ---------------------------------------------------------------------------

@dataclass
class GanttEntry:
    """
    Represents a single contiguous slice of CPU execution.

    A non-preemptive algorithm (FCFS, SJF, Priority) will produce exactly
    one GanttEntry per process. A preemptive algorithm (Round Robin) may
    produce *multiple* GanttEntry objects for the same process, because the
    process gets interrupted and resumed later.

    Attributes
    ----------
    process_id : str
        The ID of the process running during this slice. Use the special
        value "IDLE" to represent CPU idle time (e.g. waiting for a process
        to arrive).
    start : int
        The time at which this slice begins.
    end : int
        The time at which this slice ends.
    """
    process_id: str
    start: int
    end: int

    @property
    def duration(self) -> int:
        return self.end - self.start


# ---------------------------------------------------------------------------
# Process data object
# ---------------------------------------------------------------------------

@dataclass
class Process:
    """
    Represents a single process to be scheduled.

    Inputs (provided by the user / test data)
    ------------------------------------------
    pid : str
        Process identifier, e.g. "P1".
    arrival_time : int
        The time at which the process becomes ready to run (AT).
    burst_time : int
        The total amount of CPU time the process needs to complete (BT).
        This value never changes -- it represents the *original* total
        work required, even for preemptive algorithms.
    priority : int
        Priority value used only by PriorityScheduler. Lower number =
        higher priority (this is the common OS convention, e.g. UNIX
        'nice' values), but this is documented clearly so it can be
        flipped if your course defines it the opposite way.

    Mutable simulation state
    -------------------------
    remaining_time : int
        How much burst time is left to execute. Starts equal to
        burst_time. Only algorithms that can preempt (Round Robin, and
        SRTF if added later) will decrease this incrementally; all other
        algorithms decrease it to 0 in a single step.
    completion_time : Optional[int]
        The time at which the process finishes ALL of its execution (CT).
        None until the process has fully completed.
    waiting_time : Optional[int]
        WT = TAT - BT. None until computed.
    turnaround_time : Optional[int]
        TAT = CT - AT. None until computed.
    response_time : Optional[int]
        Time from arrival to the process's FIRST execution slice. This is
        not explicitly required by the assignment brief, but is a
        standard OS metric, useful for analysis/discussion, and is
        essentially "free" to compute since we already track execution
        history. Kept optional so it never breaks required outputs.
    execution_history : List[GanttEntry]
        Every CPU slice this process was given, in chronological order.
        For non-preemptive algorithms, this list will have exactly one
        entry. For Round Robin, it may have several.
    """

    pid: str
    arrival_time: int
    burst_time: int
    priority: int = 0

    # Mutable simulation state -- intentionally NOT part of the
    # constructor signature in a meaningful way; these are reset on every
    # run via reset_for_simulation() so the same Process objects can be
    # reused across multiple algorithms without manually re-creating them.
    remaining_time: int = field(init=False, default=0)
    completion_time: Optional[int] = field(init=False, default=None)
    waiting_time: Optional[int] = field(init=False, default=None)
    turnaround_time: Optional[int] = field(init=False, default=None)
    response_time: Optional[int] = field(init=False, default=None)
    execution_history: List[GanttEntry] = field(init=False, default_factory=list)

    def __post_init__(self) -> None:
        if self.burst_time <= 0:
            raise ValueError(f"Process {self.pid}: burst_time must be > 0.")
        if self.arrival_time < 0:
            raise ValueError(f"Process {self.pid}: arrival_time cannot be negative.")
        self.remaining_time = self.burst_time

    def reset_for_simulation(self) -> None:
        """
        Resets all *computed* state back to its initial form.

        This is essential because the SAME list of Process objects (the
        same mock dataset) is run through FCFS, then SJF, then Round
        Robin, then Priority, inside main(). Without resetting, the
        second algorithm would start from the leftover remaining_time /
        completion_time of the previous algorithm's run and produce
        garbage results.
        """
        self.remaining_time = self.burst_time
        self.completion_time = None
        self.waiting_time = None
        self.turnaround_time = None
        self.response_time = None
        self.execution_history = []

    def record_execution(self, start: int, end: int) -> None:
        """
        Records a slice of CPU time given to this process and updates its
        remaining burst time accordingly. Also sets response_time the
        first time this process is ever dispatched.

        Parameters
        ----------
        start : int
            Simulation clock time when this slice begins.
        end : int
            Simulation clock time when this slice ends. Must be > start.
        """
        if end <= start:
            raise ValueError(
                f"Process {self.pid}: invalid execution slice ({start} -> {end})."
            )

        if self.response_time is None:
            self.response_time = start - self.arrival_time

        self.execution_history.append(GanttEntry(self.pid, start, end))
        self.remaining_time -= (end - start)

        # Defensive clamp: floating point or off-by-one slice math should
        # never be able to push remaining_time below zero. If it does,
        # that indicates a bug in the calling scheduler, so we surface it
        # loudly rather than silently letting metrics go wrong.
        if self.remaining_time < 0:
            raise RuntimeError(
                f"Process {self.pid}: remaining_time went negative "
                f"({self.remaining_time}). This indicates a scheduler bug."
            )

    @property
    def is_complete(self) -> bool:
        return self.remaining_time == 0

    def finalize_metrics(self, completion_time: int) -> None:
        """
        Computes and stores Completion Time, Turnaround Time, and Waiting
        Time for this process, using the canonical formulas:

            Turnaround Time (TAT) = Completion Time (CT) - Arrival Time (AT)
            Waiting Time   (WT)  = Turnaround Time (TAT) - Burst Time (BT)

        Parameters
        ----------
        completion_time : int
            The simulation clock time at which this process's LAST slice
            of execution ended (i.e. when remaining_time first hit 0).
        """
        self.completion_time = completion_time

        # TAT = CT - AT
        self.turnaround_time = self.completion_time - self.arrival_time

        # WT = TAT - BT
        self.waiting_time = self.turnaround_time - self.burst_time

        # Sanity check: waiting time can never legitimately be negative.
        # A negative value here means a process "finished" before it could
        # possibly have, which is a hard scheduler bug, not a tolerable
        # rounding artifact -- so we raise rather than swallow it.
        if self.waiting_time < 0:
            raise RuntimeError(
                f"Process {self.pid}: computed negative waiting time "
                f"({self.waiting_time}). Check scheduler logic."
            )

    def __repr__(self) -> str:
        return (
            f"Process(pid={self.pid!r}, AT={self.arrival_time}, "
            f"BT={self.burst_time}, priority={self.priority}, "
            f"remaining={self.remaining_time}, CT={self.completion_time})"
        )


# ---------------------------------------------------------------------------
# Scheduler abstract base class
# ---------------------------------------------------------------------------

@dataclass
class SchedulingResult:
    """
    A clean, structured bundle of everything a scheduling run produces.
    Returned by Scheduler.run(). This is the object a GUI, a CLI report,
    or a Matplotlib chart would consume -- none of them need to know
    anything about HOW the algorithm computed these values.
    """
    algorithm_name: str
    processes: List[Process]
    gantt_chart: List[GanttEntry]
    average_waiting_time: float
    average_turnaround_time: float

    def summary_table(self) -> str:
        """Returns a simple formatted text table of per-process metrics."""
        header = f"{'PID':<6}{'AT':<6}{'BT':<6}{'CT':<6}{'TAT':<6}{'WT':<6}"
        lines = [header, "-" * len(header)]
        for p in self.processes:
            lines.append(
                f"{p.pid:<6}{p.arrival_time:<6}{p.burst_time:<6}"
                f"{p.completion_time:<6}{p.turnaround_time:<6}{p.waiting_time:<6}"
            )
        lines.append("-" * len(header))
        lines.append(f"Average Waiting Time:    {self.average_waiting_time:.2f}")
        lines.append(f"Average Turnaround Time: {self.average_turnaround_time:.2f}")
        return "\n".join(lines)


class Scheduler(ABC):
    """
    Abstract base class for all CPU scheduling algorithms.

    Subclasses MUST implement `_execute()`, which is responsible for the
    one thing that differs between algorithms: deciding the order (and,
    for preemptive algorithms, the slice sizes) in which ready processes
    are dispatched to the CPU.

    Everything else -- resetting process state, computing final metrics,
    computing averages, and assembling the SchedulingResult -- is handled
    centrally by `run()`, so every algorithm benefits from the same
    well-tested calculation logic.

    Why an ABC and not just four independent functions?
    -----------------------------------------------------
    This is exactly what Phase 4 (the "Advanced Target") in your brief
    asks for: a structure clean enough to bolt a GUI or Matplotlib chart
    onto later. A GUI can hold a `List[Scheduler]`, call `.run()` on
    whichever one the user selects from a dropdown, and render the
    returned `SchedulingResult` -- without an if/elif chain anywhere
    checking "which algorithm is this". Adding a 5th algorithm later
    (e.g. SRTF, mentioned in Part 2 of your brief) means writing ONE new
    subclass; nothing else in the codebase changes.
    """

    def __init__(self, processes: List[Process]):
        if not processes:
            raise ValueError("Scheduler requires at least one process.")
        self.processes = processes

    @property
    @abstractmethod
    def algorithm_name(self) -> str:
        """Human-readable name of the algorithm, e.g. 'First Come First Serve'."""
        raise NotImplementedError

    @abstractmethod
    def _execute(self) -> List[GanttEntry]:
        """
        Runs the actual scheduling algorithm.

        Implementations must:
          1. Iterate over self.processes (already reset and ready to go)
             in whatever order/slicing the algorithm dictates.
          2. Call `process.record_execution(start, end)` for every CPU
             slice given to a process.
          3. Call `process.finalize_metrics(completion_time)` exactly
             once per process, the moment that process's remaining_time
             reaches 0.
          4. Account for idle CPU time (when no process has arrived yet)
             by appending a GanttEntry with process_id="IDLE".
          5. Return the full chronological list of GanttEntry objects
             covering the entire simulation timeline (including IDLE
             slices), suitable for direct use by the Gantt chart
             renderer in Phase 3.

        Returns
        -------
        List[GanttEntry]
            The complete, chronologically ordered execution timeline.
        """
        raise NotImplementedError

    def run(self) -> SchedulingResult:
        """
        Public entry point. Resets process state, delegates to the
        algorithm-specific `_execute()`, then computes the aggregate
        averages shared by every algorithm.

        Returns
        -------
        SchedulingResult
            Structured bundle of per-process metrics, the Gantt chart,
            and the two required averages.
        """
        for p in self.processes:
            p.reset_for_simulation()

        gantt_chart = self._execute()

        # Defensive check: every process must have been finalized by the
        # algorithm. If not, that's a bug in the subclass, not something
        # we should silently paper over by guessing a completion time.
        unfinished = [p for p in self.processes if p.completion_time is None]
        if unfinished:
            names = ", ".join(p.pid for p in unfinished)
            raise RuntimeError(
                f"{self.algorithm_name}: the following processes were never "
                f"finalized: {names}. This indicates a bug in _execute()."
            )

        total_wt = sum(p.waiting_time for p in self.processes)
        total_tat = sum(p.turnaround_time for p in self.processes)
        n = len(self.processes)

        return SchedulingResult(
            algorithm_name=self.algorithm_name,
            processes=list(self.processes),
            gantt_chart=gantt_chart,
            average_waiting_time=total_wt / n,
            average_turnaround_time=total_tat / n,
        )
