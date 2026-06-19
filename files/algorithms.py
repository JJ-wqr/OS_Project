"""
algorithms.py
=============
Phase 2: Core Algorithms Implementation.

Concrete Scheduler subclasses:
    - FCFSScheduler       : First Come First Serve
    - SJFScheduler        : Shortest Job First (Non-preemptive)
    - RoundRobinScheduler : Round Robin with a configurable time quantum
    - PriorityScheduler   : Priority Scheduling (Non-preemptive)

Shared conventions used by every algorithm in this file
---------------------------------------------------------
1. Idle CPU time:
   If, at the current simulation clock time, no process has arrived yet
   (or all arrived processes have already completed), the CPU sits idle
   until the next process arrives. This idle gap is explicitly recorded
   as a GanttEntry with process_id="IDLE" so the Gantt chart in Phase 3
   accurately reflects gaps in execution rather than silently skipping
   time forward.

2. Deterministic tie-breaking:
   Whenever two or more processes are equally eligible to run next (e.g.
   identical arrival times in FCFS, identical burst times in SJF,
   identical priority values in PriorityScheduler), ties are broken by
   Process ID order (P1 before P2 before P3, ...). This guarantees the
   simulator produces the same, reproducible output every time it is run
   on the same input -- which matters both for grading consistency and
   for the testing strategies described in Phase 4.

3. The canonical formulas (reiterated per your instruction that every
   calculation be explicitly documented):

       Turnaround Time (TAT) = Completion Time (CT) - Arrival Time (AT)
       Waiting Time   (WT)  = Turnaround Time (TAT) - Burst Time (BT)

   These are computed in exactly one place: `Process.finalize_metrics()`
   in models.py. Every algorithm below simply calls that method at the
   correct moment (when a process's remaining_time hits 0) and never
   re-implements the arithmetic itself. This is intentional: duplicating
   the formula in four places would risk one copy silently drifting out
   of sync if the code is ever modified.
"""

from __future__ import annotations

from collections import deque
from typing import List

from models import GanttEntry, Process, Scheduler


# ---------------------------------------------------------------------------
# FCFS - First Come First Serve
# ---------------------------------------------------------------------------

class FCFSScheduler(Scheduler):
    """
    First Come First Serve (non-preemptive).

    Rule: processes are executed strictly in order of arrival time. Once a
    process starts running, it runs to completion (its full burst time)
    with no interruption.

    Tie-break: if two processes arrive at the exact same time, the one
    with the lexicographically/numerically smaller PID goes first (see
    module docstring, point 2).
    """

    @property
    def algorithm_name(self) -> str:
        return "First Come First Serve (FCFS)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []

        # Sort once by (arrival_time, pid) -- this single sort IS the
        # entire FCFS algorithm. Everything else is just simulating the
        # clock forward through that fixed order.
        ordered = sorted(self.processes, key=lambda p: (p.arrival_time, p.pid))

        clock = 0
        for process in ordered:
            # If the CPU would otherwise sit idle because this process
            # hasn't arrived yet, advance the clock and log idle time.
            if clock < process.arrival_time:
                gantt.append(GanttEntry("IDLE", clock, process.arrival_time))
                clock = process.arrival_time

            start = clock
            end = clock + process.burst_time  # full burst, non-preemptive
            process.record_execution(start, end)
            gantt.append(GanttEntry(process.pid, start, end))

            clock = end
            process.finalize_metrics(completion_time=clock)

        return gantt


# ---------------------------------------------------------------------------
# SJF - Shortest Job First (Non-preemptive)
# ---------------------------------------------------------------------------

class SJFScheduler(Scheduler):
    """
    Shortest Job First, NON-preemptive.

    Rule: at every decision point (whenever the CPU becomes free), look
    at the set of processes that have ALREADY ARRIVED but not yet run,
    and pick the one with the smallest burst_time. Once chosen, it runs
    to completion uninterrupted (that's what makes this non-preemptive --
    a shorter job arriving mid-execution does NOT pre-empt the running
    job; it just waits for the next decision point).

    Tie-break: if multiple ready processes share the same (smallest)
    burst time, the one with the smaller PID is chosen.

    This is a classic "ready queue" simulation: we do not need to know
    the whole future in advance, we just repeatedly ask "of everything
    that's available RIGHT NOW, what's shortest?".
    """

    @property
    def algorithm_name(self) -> str:
        return "Shortest Job First (SJF, Non-preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []

        remaining_pool: List[Process] = list(self.processes)
        clock = 0
        completed = 0
        n = len(self.processes)

        while completed < n:
            # Everything that has arrived by `clock` and hasn't run yet.
            ready = [p for p in remaining_pool if p.arrival_time <= clock]

            if not ready:
                # Nothing has arrived yet -- CPU is idle until the
                # earliest future arrival.
                next_arrival = min(p.arrival_time for p in remaining_pool)
                gantt.append(GanttEntry("IDLE", clock, next_arrival))
                clock = next_arrival
                continue

            # Pick shortest burst time; tie-break on PID for determinism.
            next_process = min(ready, key=lambda p: (p.burst_time, p.pid))

            start = clock
            end = clock + next_process.burst_time  # full burst, non-preemptive
            next_process.record_execution(start, end)
            gantt.append(GanttEntry(next_process.pid, start, end))

            clock = end
            next_process.finalize_metrics(completion_time=clock)

            remaining_pool.remove(next_process)
            completed += 1

        return gantt


# ---------------------------------------------------------------------------
# Round Robin
# ---------------------------------------------------------------------------

class RoundRobinScheduler(Scheduler):
    """
    Round Robin (preemptive), with a configurable time quantum.

    Rule: processes take turns running for at most `time_quantum` units
    at a time. If a process's remaining burst time exceeds the quantum,
    it is preempted (paused) after exactly `time_quantum` units and sent
    to the BACK of the ready queue; it will resume later from where it
    left off. If its remaining time is <= the quantum, it simply finishes
    during that slice.

    Implementation detail -- handling "leftover" burst time:
    Each Process tracks `remaining_time` independently of `burst_time`
    (see models.py). Every time we give a process a slice, we call
    `record_execution(start, end)`, which decrements remaining_time by
    the slice length automatically. We never mutate burst_time itself,
    since burst_time must stay as the ORIGINAL total work for TAT/WT
    calculations to be correct.

    Handling new arrivals during a running slice:
    A subtlety that's easy to get wrong: if process A is running from
    t=2 to t=6, and process B arrives at t=4, B must be added to the
    ready queue BEFORE A is re-queued (if A still has remaining time) --
    otherwise you get the wrong execution order (A would unfairly cut
    back in front of B). This implementation handles that by always
    enqueuing newly-arrived processes (in arrival-time order) BEFORE
    re-enqueuing the process that just finished its slice.

    Tie-break for processes that arrive at the exact same timestamp: PID
    order, consistent with the rest of the simulator.
    """

    def __init__(self, processes: List[Process], time_quantum: int):
        super().__init__(processes)
        if time_quantum <= 0:
            raise ValueError("time_quantum must be a positive integer.")
        self.time_quantum = time_quantum

    @property
    def algorithm_name(self) -> str:
        return f"Round Robin (Time Quantum = {self.time_quantum})"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []

        # Processes not yet arrived in simulation time, sorted so we can
        # peek/pop the earliest arrival efficiently. Ties broken by PID.
        not_arrived = sorted(self.processes, key=lambda p: (p.arrival_time, p.pid))

        ready_queue: deque[Process] = deque()
        clock = 0
        completed = 0
        n = len(self.processes)

        def admit_new_arrivals(up_to_time: int) -> None:
            """
            Moves every process whose arrival_time <= up_to_time from
            `not_arrived` into the back of the ready_queue, in arrival
            order (PID tie-break). Mutates `not_arrived` in place.
            """
            while not_arrived and not_arrived[0].arrival_time <= up_to_time:
                ready_queue.append(not_arrived.pop(0))

        # Prime the queue with whatever has arrived at time 0.
        admit_new_arrivals(clock)

        while completed < n:
            if not ready_queue:
                # Nobody is ready to run -- CPU idles until the next
                # process arrives.
                next_arrival = not_arrived[0].arrival_time
                gantt.append(GanttEntry("IDLE", clock, next_arrival))
                clock = next_arrival
                admit_new_arrivals(clock)
                continue

            current = ready_queue.popleft()

            # Run for min(quantum, what's actually left) -- this is the
            # "leftover burst time" handling: a process with less work
            # remaining than a full quantum simply finishes early instead
            # of "overrunning" into wasted CPU time.
            slice_length = min(self.time_quantum, current.remaining_time)
            start = clock
            end = clock + slice_length

            current.record_execution(start, end)
            gantt.append(GanttEntry(current.pid, start, end))
            clock = end

            # Admit anyone who arrived DURING this slice before deciding
            # whether to re-queue `current`. This preserves correct FIFO
            # fairness: a process that arrived mid-slice is logically
            # "in line" before the process that just finished its turn.
            admit_new_arrivals(clock)

            if current.is_complete:
                current.finalize_metrics(completion_time=clock)
                completed += 1
            else:
                # Still has work left -- goes to the back of the line.
                ready_queue.append(current)

        return gantt


# ---------------------------------------------------------------------------
# Priority Scheduling (Non-preemptive)
# ---------------------------------------------------------------------------

class PriorityScheduler(Scheduler):
    """
    Priority Scheduling, NON-preemptive.

    Rule: at every decision point, among all processes that have already
    arrived but not yet run, pick the one with the smallest priority
    NUMBER (this implementation follows the common OS convention that
    LOWER number = HIGHER priority, e.g. priority 1 runs before priority
    5). Once selected, the process runs to completion uninterrupted.

    NOTE ON CONVENTION: If your course defines priority the opposite way
    (higher number = higher priority), only ONE line needs to change --
    the `key=` in the `min()` call below would become a `max()` call, or
    the priority could be negated. This is called out explicitly here so
    you can adapt it confidently and explain the choice in your report.

    Tie-break: if multiple ready processes share the same priority value,
    the one with the smaller PID is chosen (consistent tie-break policy
    across the whole simulator).
    """

    @property
    def algorithm_name(self) -> str:
        return "Priority Scheduling (Non-preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []

        remaining_pool: List[Process] = list(self.processes)
        clock = 0
        completed = 0
        n = len(self.processes)

        while completed < n:
            ready = [p for p in remaining_pool if p.arrival_time <= clock]

            if not ready:
                next_arrival = min(p.arrival_time for p in remaining_pool)
                gantt.append(GanttEntry("IDLE", clock, next_arrival))
                clock = next_arrival
                continue

            # Lower priority number = runs first (see class docstring).
            next_process = min(ready, key=lambda p: (p.priority, p.pid))

            start = clock
            end = clock + next_process.burst_time  # full burst, non-preemptive
            next_process.record_execution(start, end)
            gantt.append(GanttEntry(next_process.pid, start, end))

            clock = end
            next_process.finalize_metrics(completion_time=clock)

            remaining_pool.remove(next_process)
            completed += 1

        return gantt
