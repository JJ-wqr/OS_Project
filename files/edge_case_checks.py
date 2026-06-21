#HANINA ELIAS ABDOSH - 2802516030
#JEREMY NATHANAEL GUNAWAN - 2802522960
from __future__ import annotations
import unittest
from typing import List
from algorithms import (
    FCFSScheduler,
    PriorityScheduler,
    RoundRobinScheduler,
    SJFScheduler,
    SRTFScheduler,
)
from gantt_chart import render_gantt_bracket, render_gantt_boxed
from models import GanttEntry, Process, SchedulingResult

# This creates a Process object for tests, pid = name, at = arrival time, bt = burst time, pri = priority
def _make(pid: str, at: int, bt: int, pri: int = 0) -> Process:
    return Process(pid=pid, arrival_time=at, burst_time=bt, priority=pri)

# this finds the process with the given pid in the result. 
# then it returns (completion_time, turnaround_time, waiting_time).
def _metrics(result: SchedulingResult, pid: str):

    p = next(p for p in result.processes if p.pid == pid)
    return p.completion_time, p.turnaround_time, p.waiting_time

# This converts the gantt chart blocks into a simple pid list.
# Example: ["P1", "IDLE", "P2", ...]
def _gantt_pids(result: SchedulingResult) -> List[str]:
    return [e.process_id for e in result.gantt_chart]

# This test class prepares the same process list for every FCFS test.
# It runs FCFS once and stores the output in self.result.
class TestFCFS(unittest.TestCase):
    def setUp(self):
        self.procs = [
            _make("P1", 0, 5, 2),
            _make("P2", 0, 3, 1),
            _make("P3", 2, 8, 4),
            _make("P4", 4, 6, 3),
            _make("P5", 6, 2, 5),
        ]
        self.result = FCFSScheduler(self.procs).run()

    def test_execution_order(self):
        pids = _gantt_pids(self.result)
        self.assertEqual(pids, ["P1", "P2", "P3", "P4", "P5"])
# This checks the gantt chart order for FCFS.
# If the order is wrong, the test fails.
    def test_completion_times(self):
        expected = {"P1": 5, "P2": 8, "P3": 16, "P4": 22, "P5": 24}
        for pid, ct in expected.items():
            self.assertEqual(_metrics(self.result, pid)[0], ct, f"CT mismatch for {pid}")
    
    def test_waiting_times(self):
        expected = {"P1": 0, "P2": 5, "P3": 6, "P4": 12, "P5": 16}
        for pid, wt in expected.items():
            self.assertEqual(_metrics(self.result, pid)[2], wt, f"WT mismatch for {pid}")

    def test_averages(self):
        self.assertAlmostEqual(self.result.average_waiting_time, 7.80, places=2)
        self.assertAlmostEqual(self.result.average_turnaround_time, 12.60, places=2)

    def test_formula_consistency(self):
        for p in self.result.processes:
            self.assertEqual(p.turnaround_time, p.completion_time - p.arrival_time)
            self.assertEqual(p.waiting_time, p.turnaround_time - p.burst_time)


class TestSJF(unittest.TestCase):

    def setUp(self):
        self.procs = [
            _make("P1", 0, 5),
            _make("P2", 0, 3),
            _make("P3", 2, 8),
            _make("P4", 4, 6),
            _make("P5", 6, 2),
        ]
        self.result = SJFScheduler(self.procs).run()

    def test_execution_order(self):

        pids = _gantt_pids(self.result)
        self.assertEqual(pids, ["P2", "P1", "P5", "P4", "P3"])

    def test_completion_times(self):
        expected = {"P1": 8, "P2": 3, "P3": 24, "P4": 16, "P5": 10}
        for pid, ct in expected.items():
            self.assertEqual(_metrics(self.result, pid)[0], ct, f"CT mismatch for {pid}")

    def test_averages(self):
        self.assertAlmostEqual(self.result.average_waiting_time, 5.00, places=2)
        self.assertAlmostEqual(self.result.average_turnaround_time, 9.80, places=2)

    def test_non_preemptive(self):

        pids = _gantt_pids(self.result)

        p1_idx = pids.index("P1")
        p5_idx = pids.index("P5")
        self.assertLess(p1_idx, p5_idx)


class TestRoundRobin(unittest.TestCase):

    def setUp(self):
        self.procs = [
            _make("P1", 0, 5),
            _make("P2", 0, 3),
            _make("P3", 2, 8),
            _make("P4", 4, 6),
            _make("P5", 6, 2),
        ]
        self.result = RoundRobinScheduler(self.procs, time_quantum=4).run()

    def test_completion_times(self):
        expected = {"P1": 16, "P2": 7, "P3": 22, "P4": 24, "P5": 18}
        for pid, ct in expected.items():
            self.assertEqual(_metrics(self.result, pid)[0], ct, f"CT mismatch for {pid}")

    def test_averages(self):
        self.assertAlmostEqual(self.result.average_waiting_time, 10.20, places=2)
        self.assertAlmostEqual(self.result.average_turnaround_time, 15.00, places=2)

    def test_formula_consistency(self):
        for p in self.result.processes:
            self.assertEqual(p.turnaround_time, p.completion_time - p.arrival_time)
            self.assertEqual(p.waiting_time, p.turnaround_time - p.burst_time)

    def test_large_quantum_equals_fcfs(self):

        procs_rr   = [_make("P1", 0, 3), _make("P2", 1, 4), _make("P3", 2, 2)]
        procs_fcfs = [_make("P1", 0, 3), _make("P2", 1, 4), _make("P3", 2, 2)]
        rr_res   = RoundRobinScheduler(procs_rr,   time_quantum=999).run()
        fcfs_res = FCFSScheduler(procs_fcfs).run()
        rr_m   = [(p.pid, p.waiting_time, p.turnaround_time) for p in rr_res.processes]
        fcfs_m = [(p.pid, p.waiting_time, p.turnaround_time) for p in fcfs_res.processes]
        self.assertEqual(rr_m, fcfs_m)

    def test_quantum_gt_burst_completes_in_one_slice(self):

        procs = [_make("P1", 0, 2)]
        result = RoundRobinScheduler(procs, time_quantum=10).run()
        self.assertEqual(len(result.gantt_chart), 1)
        self.assertEqual(result.gantt_chart[0].end, 2)

    def test_arrival_ordering_during_slice(self):

        procs = [_make("P1", 0, 5), _make("P2", 1, 2)]
        result = RoundRobinScheduler(procs, time_quantum=3).run()
        pids = _gantt_pids(result)
        self.assertEqual(pids[0], "P1")
        self.assertEqual(pids[1], "P2")
        self.assertEqual(pids[2], "P1")


class TestPriority(unittest.TestCase):

    def setUp(self):
        self.procs = [
            _make("P1", 0, 5, 2),
            _make("P2", 0, 3, 1),
            _make("P3", 2, 8, 4),
            _make("P4", 4, 6, 3),
            _make("P5", 6, 2, 5),
        ]
        self.result = PriorityScheduler(self.procs).run()

    def test_execution_order(self):


        pids = _gantt_pids(self.result)
        self.assertEqual(pids, ["P2", "P1", "P4", "P3", "P5"])

    def test_completion_times(self):
        expected = {"P1": 8, "P2": 3, "P3": 22, "P4": 14, "P5": 24}
        for pid, ct in expected.items():
            self.assertEqual(_metrics(self.result, pid)[0], ct, f"CT mismatch for {pid}")

    def test_averages(self):
        self.assertAlmostEqual(self.result.average_waiting_time, 7.00, places=2)
        self.assertAlmostEqual(self.result.average_turnaround_time, 11.80, places=2)


class TestSRTF(unittest.TestCase):

    def test_preemption_occurs(self):

        procs = [_make("P1", 0, 7), _make("P2", 2, 3)]
        result = SRTFScheduler(procs).run()
        gantt_pids = _gantt_pids(result)

        self.assertEqual(gantt_pids[0], "P1")
        self.assertIn("P2", gantt_pids)
        p2_idx = gantt_pids.index("P2")

        self.assertIn("P1", gantt_pids[p2_idx + 1:])

    def test_formula_consistency(self):
        procs = [_make("P1", 0, 5, 2), _make("P2", 1, 3, 1), _make("P3", 3, 4, 3)]
        result = SRTFScheduler(procs).run()
        for p in result.processes:
            self.assertEqual(p.turnaround_time, p.completion_time - p.arrival_time)
            self.assertEqual(p.waiting_time, p.turnaround_time - p.burst_time)
            self.assertGreaterEqual(p.waiting_time, 0)


class TestEdgeCases(unittest.TestCase):

    ALL_SCHEDULERS = [FCFSScheduler, SJFScheduler, PriorityScheduler]

    def test_single_process_all_algorithms(self):

        for cls in self.ALL_SCHEDULERS:
            procs = [_make("P1", 3, 7)]
            result = cls(procs).run()
            p = result.processes[0]
            self.assertEqual(p.completion_time, 10,   msg=f"CT wrong in {cls.__name__}")
            self.assertEqual(p.waiting_time, 0,        msg=f"WT wrong in {cls.__name__}")
            self.assertEqual(p.turnaround_time, 7,     msg=f"TAT wrong in {cls.__name__}")

    def test_single_process_rr(self):

        for q in (1, 3, 100):
            procs = [_make("P1", 0, 5)]
            result = RoundRobinScheduler(procs, time_quantum=q).run()
            p = result.processes[0]
            self.assertEqual(p.completion_time, 5)
            self.assertEqual(p.waiting_time, 0)

    def test_cpu_idle_gap(self):

        procs = [_make("P1", 5, 3), _make("P2", 10, 2)]
        result = FCFSScheduler(procs).run()
        self.assertEqual(result.gantt_chart[0].process_id, "IDLE")
        self.assertEqual(result.gantt_chart[0].start, 0)
        self.assertEqual(result.gantt_chart[0].end, 5)

    def test_simultaneous_arrivals_tiebreak(self):

        procs = [_make("P3", 0, 2), _make("P1", 0, 2), _make("P2", 0, 2)]
        result = FCFSScheduler(procs).run()
        pids = _gantt_pids(result)
        self.assertEqual(pids, ["P1", "P2", "P3"])

    def test_all_arrive_at_same_time(self):

        procs = [_make(f"P{i}", 0, i + 1) for i in range(1, 5)]
        for cls in self.ALL_SCHEDULERS:
            result = cls(procs).run()
            self.assertNotIn("IDLE", _gantt_pids(result), msg=f"{cls.__name__} has spurious IDLE")

    def test_waiting_time_never_negative(self):

        procs = [
            _make("P1", 0, 5, 2),
            _make("P2", 1, 3, 1),
            _make("P3", 2, 8, 3),
        ]
        for cls in self.ALL_SCHEDULERS:
            result = cls(list(procs)).run()
            for p in result.processes:
                self.assertGreaterEqual(p.waiting_time, 0,
                    msg=f"Negative WT for {p.pid} in {cls.__name__}")

    def test_rr_quantum_eq_burst_single_slice(self):

        procs = [_make("P1", 0, 4), _make("P2", 0, 4)]
        result = RoundRobinScheduler(procs, time_quantum=4).run()
        pids = _gantt_pids(result)

        self.assertEqual(pids.count("P1"), 1)
        self.assertEqual(pids.count("P2"), 1)

    def test_formula_holds_for_all_algorithms_all_inputs(self):

        procs = [
            _make("P1", 0, 5, 2),
            _make("P2", 0, 3, 1),
            _make("P3", 2, 8, 4),
        ]
        schedulers = [
            FCFSScheduler(list(procs)),
            SJFScheduler(list(procs)),
            PriorityScheduler(list(procs)),
            RoundRobinScheduler(list(procs), time_quantum=3),
            SRTFScheduler(list(procs)),
        ]
        for sched in schedulers:
            result = sched.run()
            for p in result.processes:
                self.assertEqual(
                    p.turnaround_time,
                    p.completion_time - p.arrival_time,
                    msg=f"TAT formula failed for {p.pid} in {sched.algorithm_name}",
                )
                self.assertEqual(
                    p.waiting_time,
                    p.turnaround_time - p.burst_time,
                    msg=f"WT formula failed for {p.pid} in {sched.algorithm_name}",
                )

    def test_gantt_is_contiguous(self):

        procs = [_make("P1", 0, 5), _make("P2", 3, 3), _make("P3", 7, 4)]
        for cls in [FCFSScheduler, SJFScheduler, PriorityScheduler]:
            result = cls(procs).run()
            for i in range(1, len(result.gantt_chart)):
                prev = result.gantt_chart[i - 1]
                curr = result.gantt_chart[i]
                self.assertAlmostEqual(
                    prev.end, curr.start,
                    msg=f"Gap in Gantt chart at [{prev.end}, {curr.start}] in {cls.__name__}",
                )

    def test_empty_list_raises(self):

        for cls in self.ALL_SCHEDULERS:
            with self.assertRaises(ValueError, msg=f"{cls.__name__} should raise on empty list"):
                cls([])

    def test_invalid_quantum_raises(self):

        procs = [_make("P1", 0, 5)]
        with self.assertRaises(ValueError):
            RoundRobinScheduler(procs, time_quantum=0)
        with self.assertRaises(ValueError):
            RoundRobinScheduler(procs, time_quantum=-1)

    def test_negative_arrival_raises(self):

        with self.assertRaises(ValueError):
            _make("P1", -1, 5)

    def test_zero_burst_raises(self):

        with self.assertRaises(ValueError):
            _make("P1", 0, 0)

    def test_negative_burst_raises(self):

        with self.assertRaises(ValueError):
            _make("P1", 0, -3)

    def test_negative_priority_raises(self):

        with self.assertRaises(ValueError):
            _make("P1", 0, 5, pri=-1)

    def test_duplicate_pid_raises(self):

        procs = [_make("P1", 0, 5), _make("P1", 2, 3)]
        for cls in self.ALL_SCHEDULERS:
            with self.assertRaises(ValueError, msg=f"{cls.__name__} should reject duplicate PIDs"):
                cls(list(procs))

    def test_duplicate_pid_raises_round_robin(self):

        procs = [_make("P1", 0, 5), _make("P1", 2, 3)]
        with self.assertRaises(ValueError):
            RoundRobinScheduler(procs, time_quantum=2)


class TestGanttRendering(unittest.TestCase):

    def setUp(self):
        self.gantt = [
            GanttEntry("P1",   0,  5),
            GanttEntry("P2",   5,  8),
            GanttEntry("IDLE", 8, 10),
            GanttEntry("P3",  10, 18),
        ]

    def test_bracket_format(self):
        out = render_gantt_bracket(self.gantt)
        self.assertEqual(out, "[P1|0-5][P2|5-8][IDLE|8-10][P3|10-18]")

    def test_boxed_two_lines(self):
        out = render_gantt_boxed(self.gantt)
        lines = out.splitlines()
        self.assertEqual(len(lines), 2, "Boxed Gantt must produce exactly 2 lines")

    def test_boxed_ruler_contains_all_times(self):

        out = render_gantt_boxed(self.gantt)
        ruler = out.splitlines()[1]
        for t in ("0", "5", "8", "10", "18"):
            self.assertIn(t, ruler, f"Timestamp {t} missing from ruler")

    def test_empty_gantt(self):
        self.assertEqual(render_gantt_bracket([]), "(empty timeline)")
        self.assertEqual(render_gantt_boxed([]), "(empty timeline)")


if __name__ == "__main__":
    unittest.main(verbosity=2)

