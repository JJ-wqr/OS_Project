from __future__ import annotations

from collections import deque
from typing import List

from models import GanttEntry, Process, Scheduler

#start of FCFS algo

class FCFSScheduler(Scheduler):
# This runs processes in the order they arrive.
# It is NOT preemptive, so once a process starts, it runs until it finishes.
    @property
    def algorithm_name(self) -> str:
        return "First Come First Serve (FCFS)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []

        # Make new list "ordered", then shorts arrival_time first 
        #If two process arrive at same time, smaller PID goes first
        ordered = sorted(self.processes, key=lambda p: (p.arrival_time, p.pid))

        #clock below is the current cpu time, for each process in arrival order it will execute
        clock: float = 0.0
        for process in ordered:
            # If cpu is free before next process, add "IdlE" to ganttchart, then move clock forward to the arrival time
            if clock < process.arrival_time:
                gantt.append(GanttEntry("IDLE", clock, process.arrival_time))
                clock = process.arrival_time
            # When process begin running, end when (start + burst_time) finish, then record that execution in Process object
            start = clock
            end = clock + process.burst_time
            process.record_execution(start, end)
            gantt.append(GanttEntry(process.pid, start, end))
            #move clock to finish time, compute completion for the process
            clock = end
            process.finalize_metrics(completion_time=clock)

        return gantt
        #end of FCFS algo

# SJF, picks ready process with smallest burst_time, does not interrupt a process once it starts (running process)
class SJFScheduler(Scheduler):


    @property
    def algorithm_name(self) -> str:
        return "Shortest Job First (SJF, Non-preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        # makes working list of processes not finished yet
        pool: List[Process] = list(self.processes)
        clock: float = 0.0
        completed: int = 0
        n: int = len(self.processes)
        
        #while completed reapests until all process are complete
        while completed < n:
            #Find all processes that have arried by current clock time
            ready = [p for p in pool if p.arrival_time <= clock]

            if not ready:
                #if it is not ready then cpu stay idle.
                # It then move lcock to next process arrival then loop
                next_arrival = min(p.arrival_time for p in pool)
                gantt.append(GanttEntry("IDLE", clock, next_arrival))
                clock = next_arrival
                continue

            #Pick the process iwht smallest burst_time
            #if burst time ties, smaller pid goes
            chosen = min(ready, key=lambda p: (p.burst_time, p.pid))

            #run chosen process from start to end, or full burst, record then add gantt block
            start = clock
            end = clock + chosen.burst_time
            chosen.record_execution(start, end)
            gantt.append(GanttEntry(chosen.pid, start, end))

            #clock = end below block function updates clock to finish time, compute metrics, remove pool 
            #removing pool so that it will not run again
            clock = end
            chosen.finalize_metrics(completion_time=clock)

            pool.remove(chosen)
            completed += 1

        return gantt
# end of SJF


#RR preemptive use time_quantum
#run in a loop using queue
# eacj process run for repending on the time_quantum, then goes back to queue (iuf not finish)
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

        # not_arrived holds process not yet available sorted by arrival
        # redy is queue for processes that are well ready to run
        not_arrived = sorted(self.processes, key=lambda p: (p.arrival_time, p.pid))
        ready: deque[Process] = deque()
        clock: float = 0.0
        completed: int = 0
        n: int = len(self.processes)
        # move processes that arrived by time "up_to" into ready queue
        def admit_arrivals(up_to: float) -> None:

            while not_arrived and not_arrived[0].arrival_time <= up_to:
                ready.append(not_arrived.pop(0))

        #admit arrival puts arrivals that already exist at time 0 into ready
        admit_arrivals(clock)

        while completed < n:
            if not ready:

                if not not_arrived:
                    break
                #if ready queue empty but exists future processes, add idle block until next arrival
                #then, move clock to that arrival and admit newly arrived processes
                next_arr = not_arrived[0].arrival_time
                gantt.append(GanttEntry("IDLE", clock, next_arr))
                clock = next_arr
                admit_arrivals(clock)
                continue
            #take next process from the front of the queue
            current = ready.popleft()

            #decide how long this round runs, either full quantum or less if finishes aealy
            # record and chart and update lclock
            slice_len = min(self.time_quantum, current.remaining_time)
            start = clock
            end = clock + slice_len

            current.record_execution(start, end)
            gantt.append(GanttEntry(current.pid, start, end))
            clock = end
            # add any proceses that arrive during this time sliace
            admit_arrivals(clock)

            if current.is_complete:
                current.finalize_metrics(completion_time=clock)
                completed += 1
            else:

                ready.append(current)
                # if finish, send back to the queue

        return gantt
# end of algorothjm


#priority sscheduling non-preemtive

#pick process with the best (smallest priority_)
# run chosen process to completion (nopreempetion)
class PriorityScheduler(Scheduler):


    @property
    def algorithm_name(self) -> str:
        return "Priority Scheduling (Non-preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        # proccesses not finished yet (pool: list[process])
        pool: List[Process] = list(self.processes)
        clock: float = 0.0
        completed: int = 0
        n: int = len(self.processes)

        while completed < n:
            #build ready list based on arrival_time 
            ready = [p for p in pool if p.arrival_time <= clock]
            # if not ready, cpu waits until next arrival
            if not ready:
                next_arrival = min(p.arrival_time for p in pool)
                gantt.append(GanttEntry("IDLE", clock, next_arrival))
                clock = next_arrival
                continue

            # pick the smallest priority value, tie-break using PID
            chosen = min(ready, key=lambda p: (p.priority, p.pid))
            # run chosen for full burst time, record and add gantt block, move clock forward
            start = clock
            end = clock + chosen.burst_time
            chosen.record_execution(start, end)
            gantt.append(GanttEntry(chosen.pid, start, end))

            clock = end
            chosen.finalize_metrics(completion_time=clock)
            
            #finalize the metrics, remove from pool, update complted count
            pool.remove(chosen)
            completed += 1

        return gantt
# end of algorithm


# SRTF, shorted remaining time first, it is preemptive and 1 unit at a time
# at every time unit, it picks ready process with the smallest remaining time
# if different process becomes better, it will switch - preemption
class SRTFScheduler(Scheduler):


    @property
    def algorithm_name(self) -> str:
        return "Shortest Remaining Time First (SRTF, Preemptive)"

    def _execute(self) -> List[GanttEntry]:
        gantt: List[GanttEntry] = []
        pool: List[Process] = list(self.processes)
        clock: float = 0.0
        completed: int = 0
        n: int = len(self.processes)

        # current pid stores which process is currently running
        # current start stores when crrent run segment starts
        current_pid: str = ""
        current_start: float = 0.0

        # when switching processes or going idle, it saves finished running segment to gantt
        def commit_slice(end: float) -> None:
            if current_pid and end > current_start:
                gantt.append(GanttEntry(current_pid, current_start, end))

        while completed < n:
            #ready list contains arrived and unfinished processes
            ready = [p for p in pool if p.arrival_time <= clock and not p.is_complete]
            if not ready:
                future = [p.arrival_time for p in pool if not p.is_complete]
                if not future:
                    break
                next_arr = min(future)
                commit_slice(clock)
                gantt.append(GanttEntry("IDLE", clock, next_arr))
                current_pid = ""
                clock = next_arr
                continue
            #this block functions that if nothing is ready, it goes to the next arrival
            # commit wwhat was running up to now
            # add idle segment until next arrival
            # reset current running process

            #pick process with smallest remaining_time, tie-break by pid
            chosen = min(ready, key=lambda p: (p.remaining_time, p.pid))

            # this block functions that if we need to switch processes, it commit old segment and start a new segment for the new process
            if chosen.pid != current_pid:
                commit_slice(clock)
                current_pid = chosen.pid
                current_start = clock

            # run chosen for exactly 1 time unit, move clock forward by 1
            chosen.record_execution(clock, clock + 1)
            clock += 1

            if chosen.is_complete:
                commit_slice(clock)
                current_pid = ""
                chosen.finalize_metrics(completion_time=clock)
                pool.remove(chosen)
                completed += 1
                #when chosen has finished after this unit, commit final segment, compute metrics, remove from pool and count completion

        return gantt
# end of algorithm 
