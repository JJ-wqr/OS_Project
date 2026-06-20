

from __future__ import annotations
from typing import List
from models import GanttEntry
# This is a list of terminal colour codes (ANSI escape codes).
# They are used for printing different process IDs in different colours.
_ANSI_COLOURS = [
    "\033[36m", #cyan
    "\033[33m", #yellow
    "\033[32m", #green
    "\033[35m",# purple/magenta
    "\033[34m", #blue
    "\033[31m", #red
    "\033[96m",# bright cyan
    "\033[93m", #bright yellow
    "\033[92m", #bright green
    "\033[95m", #bright magenta
]
# This turns colour back off (so later text does not keep the same colour).
_ANSI_RESET  = "\033[0m"
#This is the colour code used specifically for the "IDLE" blocks.
# It is usually a grey colour so idle time looks different from real processes
_ANSI_IDLE   = "\033[90m"


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
    boundaries: list[tuple[int, float]] = []

    for entry in gantt:
        label = entry.process_id
        inner = max(MIN_BOX, len(label) + 2)
        pad_l = (inner - len(label)) // 2
        pad_r = inner - len(label) - pad_l

        boundaries.append((len(top), entry.start))
        top += " " * pad_l + label + " " * pad_r + "|"


    boundaries.append((len(top) - 1, gantt[-1].end))


    ruler = list(" " * len(top))
    for col, t in boundaries:
        label = _fmt_time(t)

        for i, ch in enumerate(label):
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


    seen: dict[str, list[str]] = {}
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

