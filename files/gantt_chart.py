#HANINA ELIAS ABDOSH - 2802516030
#JEREMY NATHANAEL GUNAWAN - 2802522960
from __future__ import annotations

from typing import List

from models import GanttEntry


# ANSI terminal color codes (used to print different processes in different colors)
_ANSI_COLOURS = [
    "\033[36m", # cyan
    "\033[33m", # yellow
    "\033[32m", # green
    "\033[35m",# purple/magenta
    "\033[34m", #blue
    "\033[31m", #red
    "\033[96m", # bright cyan
    "\033[93m", # bright yellow
    "\033[92m", # bright green
    "\033[95m", # bright magenta
]
# Reset ANSI styles back to normal (so colors do not "leak" into later text)
_ANSI_RESET  = "\033[0m"
# Color used for the "IDLE" blocks (CPU waiting time)
_ANSI_IDLE   = "\033[90m"


def _colour_for_pid(pid: str, colour_map: dict) -> str:

    # Keep IDLE always the same color
    if pid == "IDLE":
        return _ANSI_IDLE
    # First time we see a pid, pick the next color from the list
    if pid not in colour_map:
        colour_map[pid] = _ANSI_COLOURS[len(colour_map) % len(_ANSI_COLOURS)]
    # Return the cached color for this pid
    return colour_map[pid]


def _fmt_time(t: float) -> str:

    # If t is a whole number, show it like "5"
    # Otherwise show with 2 decimals like "5.50"
    return str(int(t)) if t == int(t) else f"{t:.2f}"


def render_gantt_bracket(gantt: List[GanttEntry]) -> str:

    # No blocks means no timeline
    if not gantt:
        return "(empty timeline)"
    # Build a string like: [P1|0-5][P2|5-8]...
    return "".join(
        f"[{e.process_id}|{_fmt_time(e.start)}-{_fmt_time(e.end)}]"
        for e in gantt
    )


def render_gantt_boxed(gantt: List[GanttEntry]) -> str:

    # No blocks means no timeline
    if not gantt:
        return "(empty timeline)"

    MIN_BOX = 4

    # Top line starts with a left border
    top = "|"

    # boundaries holds: (column_where_time_string_starts, time_value)
    boundaries: list[tuple[int, float]] = []

    # Build the top boxed labels and record where each start time goes
    for entry in gantt:
        label = entry.process_id
        # Make sure each box is at least MIN_BOX wide
        inner = max(MIN_BOX, len(label) + 2)

        # split padding left/right so label fits inside the box
        pad_l = (inner - len(label)) // 2
        pad_r = inner - len(label) - pad_l

        # record start time location in the top string
        boundaries.append((len(top), entry.start))

        # add a whole box segment into the top string
        top += " " * pad_l + label + " " * pad_r + "|"

    # Add the last time (right side end time) so the ruler shows final end
    boundaries.append((len(top) - 1, gantt[-1].end))

    # Create a ruler line full of spaces, then place time digits into it
    ruler = list(" " * len(top))

    for col, t in boundaries:
        label = _fmt_time(t)

        # write each character of the time label into the ruler
        for i, ch in enumerate(label):
            pos = col + i
            if pos < len(ruler):
                ruler[pos] = ch
            else:
                ruler.append(ch)

    # Final output is: top line + newline + ruler line (trim extra spaces)
    return top + "\n" + "".join(ruler).rstrip()


def render_gantt_coloured(gantt: List[GanttEntry]) -> str:

    # No blocks means no timeline
    if not gantt:
        return "(empty timeline)"

    # pid -> chosen color code
    colour_map: dict = {}

    # pieces are joined at the end
    parts = []

    # Render each block with its color
    for e in gantt:
        c = _colour_for_pid(e.process_id, colour_map)

        # Wrap each block in colour code, and reset after the block
        parts.append(
            f"{c}[{e.process_id}|{_fmt_time(e.start)}-{_fmt_time(e.end)}]{_ANSI_RESET}"
        )

    # Join all colored blocks together
    return "".join(parts)


def render_execution_slices(gantt: List[GanttEntry]) -> str:

    # No blocks means no timeline
    if not gantt:
        return "(empty timeline)"

    # Map pid -> list of slice strings like "[0-3]"
    seen: dict[str, list[str]] = {}

    # Collect slices grouped by process_id
    for e in gantt:
        s = f"[{_fmt_time(e.start)}-{_fmt_time(e.end)}]"
        if e.process_id not in seen:
            seen[e.process_id] = []
        seen[e.process_id].append(s)

    # Find widest pid for aligned table formatting
    col_w = max(len(pid) for pid in seen)

    # Header separator line
    sep = "-" * col_w + "  " + "-" * 40
    lines = [f"{'PID':<{col_w}}  Slices", sep]

    # Add one line per pid
    for pid, slices in seen.items():
        lines.append(f"{pid:<{col_w}}  {'  '.join(slices)}")

    # Join lines with newlines
    return "\n".join(lines)
