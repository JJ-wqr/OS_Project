"""
gantt_chart.py
==============
Phase 3 (part 1): Text-Based Gantt Chart utility.

Renders a List[GanttEntry] (as produced by any Scheduler.run()) into a
clean, readable text-based timeline, e.g.:

    [P1|0-5][P2|5-12][IDLE|12-15][P3|15-20]

Also renders an aligned ruler underneath showing the timestamps at every
segment boundary, e.g.:

    [ P1 ][   P2    ][IDLE][  P3  ]
    0    5          12   15      20

Kept as a standalone module (rather than a method on Scheduler) on
purpose: this is presentation/formatting logic, completely decoupled
from scheduling logic. A future Tkinter or Matplotlib visualization can
read the exact same List[GanttEntry] data and render it as colored boxes
instead of text -- this module would simply sit alongside that
visualization as the "console fallback", not be replaced by it.
"""

from __future__ import annotations

from typing import List

from models import GanttEntry


def render_gantt_chart(gantt_chart: List[GanttEntry]) -> str:
    """
    Renders a bracketed, single-line Gantt chart, e.g.:

        [P1|0-5][P2|5-12][P3|12-20]

    Consecutive entries for the same process/IDLE block are NOT merged
    here on purpose -- Round Robin legitimately produces multiple
    separate entries for the same process (e.g. P1 running, then other
    processes, then P1 running again), and merging them would visually
    hide the preemption that Round Robin is specifically meant to show.

    Parameters
    ----------
    gantt_chart : List[GanttEntry]
        Chronologically ordered list of execution/idle slices, as
        returned inside a SchedulingResult.

    Returns
    -------
    str
        A single-line text representation of the timeline.
    """
    if not gantt_chart:
        return "(empty timeline)"

    return "".join(
        f"[{entry.process_id}|{entry.start}-{entry.end}]" for entry in gantt_chart
    )


def render_gantt_chart_boxed(gantt_chart: List[GanttEntry]) -> str:
    """
    Renders a two-line "boxed" Gantt chart: a row of proportionally-sized
    boxes on top, and a ruler of timestamps aligned to each boundary
    underneath, e.g.:

        | P1  |   P2   | P3 |
        0     5        12   16

    This is a nicer visual for short timelines but can get visually
    noisy for charts with many very short slices (e.g. Round Robin with
    a small quantum and many processes) -- in that case
    `render_gantt_chart()` (the bracket style) remains more reliable and
    readable, which is why both are provided.

    Parameters
    ----------
    gantt_chart : List[GanttEntry]
        Chronologically ordered list of execution/idle slices.

    Returns
    -------
    str
        A two-line string: boxes on line 1, time ruler on line 2.
    """
    if not gantt_chart:
        return "(empty timeline)"

    # Build each box wide enough to fit its label, with a minimum width
    # so very short slices (e.g. quantum=1) still render legibly.
    MIN_WIDTH = 4
    top_line = "|"
    bottom_line = ""
    cursor_for_bottom = 0

    for entry in gantt_chart:
        label = entry.process_id
        box_width = max(MIN_WIDTH, len(label) + 2)
        padding_total = box_width - len(label)
        left_pad = padding_total // 2
        right_pad = padding_total - left_pad
        top_line += (" " * left_pad) + label + (" " * right_pad) + "|"

        # Place the start timestamp aligned under the left edge of this box.
        start_label = str(entry.start)
        # Number of characters already written to bottom_line vs. where
        # this box started on top_line (accounting for the leading "|").
        target_col = len(top_line) - box_width - 1
        if len(bottom_line) < target_col:
            bottom_line += " " * (target_col - len(bottom_line))
        bottom_line += start_label
        cursor_for_bottom = len(bottom_line)

    # Final timestamp (end of the very last entry) goes at the far right.
    final_time = str(gantt_chart[-1].end)
    final_col = len(top_line) - 1
    if len(bottom_line) < final_col:
        bottom_line += " " * (final_col - len(bottom_line))
    bottom_line += final_time

    return top_line + "\n" + bottom_line
