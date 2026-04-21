"""
renderer.py — Professional 2D Floor Plan Renderer
==================================================
Matplotlib pe based production-quality floor plan rendering.

Features:
  - Proper room polygons with wall thickness
  - Direction-based rotation
  - Realistic door arcs (hinge + swing)
  - Window symbols (double line + glass)
  - Dimension annotations
  - North arrow compass
  - Room area labels
  - Professional architectural styling
"""

from __future__ import annotations
import math
import io
from typing import Dict, List, Optional, Tuple

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, Arc, Rectangle, Polygon, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.patheffects import withStroke
import matplotlib.patheffects as pe
from matplotlib.gridspec import GridSpec

from vastu import audit_layout, overall_vastu_score


# ─────────────────────────────────────────────────────────────────
# Color & Style Constants
# ─────────────────────────────────────────────────────────────────

WALL_COLOR      = "#2C3E50"
WALL_LW         = 3.5
DOOR_COLOR      = "#8B4513"
DOOR_LW         = 2.0
WINDOW_COLOR    = "#1A6EA3"
WINDOW_LW       = 3.5
LABEL_COLOR     = "#1a1a2e"
DIM_COLOR       = "#555555"
COMPASS_RED     = "#C0392B"
BG_COLOR        = "#FAFAFA"
GRID_COLOR      = "#E0E0E0"

FONT_ROOM       = {"size": 8,  "weight": "bold",   "family": "DejaVu Sans"}
FONT_AREA       = {"size": 6.5,"style":  "italic",  "family": "DejaVu Sans"}
FONT_DIM        = {"size": 7,  "weight": "normal",  "family": "DejaVu Sans Mono"}
FONT_TITLE      = {"size": 14, "weight": "bold",    "family": "DejaVu Sans"}
FONT_SUBTITLE   = {"size": 9,  "weight": "normal",  "family": "DejaVu Sans"}


# ─────────────────────────────────────────────────────────────────
# Geometry Utilities
# ─────────────────────────────────────────────────────────────────

def _rotate_point(x: float, y: float, cx: float, cy: float,
                  angle_deg: float) -> Tuple[float, float]:
    rad = math.radians(angle_deg)
    dx, dy = x - cx, y - cy
    return (
        cx + dx * math.cos(rad) - dy * math.sin(rad),
        cy + dx * math.sin(rad) + dy * math.cos(rad),
    )


def _rotate_corners(corners: List[Tuple], cx: float, cy: float,
                    angle: float) -> List[Tuple]:
    return [_rotate_point(x, y, cx, cy, angle) for x, y in corners]


def _rect_corners(x, y, w, h) -> List[Tuple]:
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


# ─────────────────────────────────────────────────────────────────
# Drawing Primitives
# ─────────────────────────────────────────────────────────────────

def _draw_room(ax, room: Dict, cx: float, cy: float, angle: float, wall_lw: float):
    """Room rectangle draw karo — rotated polygon as filled patch"""
    x, y, w, h = room["x"], room["y"], room["w"], room["h"]
    color = room.get("color", "#f0f0f0")

    corners = _rect_corners(x, y, w, h)
    rot_corners = _rotate_corners(corners, cx, cy, angle)

    poly = Polygon(
        rot_corners,
        closed=True,
        facecolor=color,
        edgecolor=WALL_COLOR,
        linewidth=wall_lw,
        alpha=0.88,
        zorder=2,
    )
    ax.add_patch(poly)

    # Room label
    rcx = sum(p[0] for p in rot_corners) / 4
    rcy = sum(p[1] for p in rot_corners) / 4

    label = room.get("label", "")
    area  = room["w"] * room["h"]

    # Multi-line label: name + area
    ax.text(
        rcx, rcy + 0.5, label,
        ha="center", va="center",
        fontsize=FONT_ROOM["size"],
        fontweight=FONT_ROOM["weight"],
        color=LABEL_COLOR,
        zorder=5,
        wrap=True,
        path_effects=[withStroke(linewidth=2, foreground="white")]
    )
    ax.text(
        rcx, rcy - 0.9,
        f"{area:.0f} sq ft",
        ha="center", va="center",
        fontsize=FONT_AREA["size"],
        fontstyle=FONT_AREA["style"],
        color="#555555",
        zorder=5,
    )


def _draw_door(ax, door: Dict, room: Dict, cx: float, cy: float,
               angle: float, door_size: float = 3.0):
    """
    Architectural door symbol:
    - Thin line = door panel
    - Quarter-circle arc = swing arc
    """
    wall = door.get("wall", "bottom")
    dx   = door.get("x", room["x"])
    dy   = door.get("y", room["y"])
    dw   = door.get("width", door_size)
    dtype = door.get("type", "internal")

    color = "#8B0000" if dtype == "main" else DOOR_COLOR
    lw    = 2.5 if dtype == "main" else 1.8

    # Hinge point aur swing direction
    if wall == "bottom":
        hx, hy   = dx, dy
        ex, ey   = dx + dw, dy         # door end
        arc_theta1, arc_theta2 = 0, 90
        arc_cx, arc_cy = hx, hy
    elif wall == "top":
        hx, hy   = dx, dy
        ex, ey   = dx + dw, dy
        arc_theta1, arc_theta2 = 270, 360
        arc_cx, arc_cy = hx, hy
    elif wall == "left":
        hx, hy   = dx, dy
        ex, ey   = dx, dy + dw
        arc_theta1, arc_theta2 = 0, 90
        arc_cx, arc_cy = hx, hy
    else:  # right
        hx, hy   = dx, dy
        ex, ey   = dx, dy + dw
        arc_theta1, arc_theta2 = 90, 180
        arc_cx, arc_cy = hx, hy

    # Rotate hinge, end, arc-centre
    rhx, rhy = _rotate_point(hx, hy, cx, cy, angle)
    rex, rey = _rotate_point(ex, ey, cx, cy, angle)
    rax, ray = _rotate_point(arc_cx, arc_cy, cx, cy, angle)

    # Door panel line
    ax.plot([rhx, rex], [rhy, rey], color=color, lw=lw, solid_capstyle="round", zorder=4)

    # Swing arc (approximated as small arc patch)
    arc = Arc(
        (rax, ray), width=dw * 2, height=dw * 2,
        angle=angle,
        theta1=arc_theta1, theta2=arc_theta2,
        color=color, lw=1.2, linestyle="--", zorder=4
    )
    ax.add_patch(arc)


def _draw_window(ax, window: Dict, room: Dict, cx: float, cy: float, angle: float):
    """
    Architectural window symbol:
    Double parallel line with glass infill
    """
    wall  = window.get("wall", "top")
    wx    = window.get("x", room["x"])
    wy    = window.get("y", room["y"])
    ww    = window.get("width", 3.0)
    wtype = window.get("type", "casement")

    gap   = 0.35   # gap between double lines

    if wall in ("top", "bottom"):
        # Horizontal window
        p1 = (wx,      wy)
        p2 = (wx + ww, wy)
        p3 = (wx,      wy + gap)
        p4 = (wx + ww, wy + gap)
        fill_pts = [(wx, wy), (wx + ww, wy), (wx + ww, wy + gap), (wx, wy + gap)]
    else:
        # Vertical window
        p1 = (wx,       wy)
        p2 = (wx,       wy + ww)
        p3 = (wx + gap, wy)
        p4 = (wx + gap, wy + ww)
        fill_pts = [(wx, wy), (wx + gap, wy), (wx + gap, wy + ww), (wx, wy + ww)]

    # Rotate all points
    rp1 = _rotate_point(*p1, cx, cy, angle)
    rp2 = _rotate_point(*p2, cx, cy, angle)
    rp3 = _rotate_point(*p3, cx, cy, angle)
    rp4 = _rotate_point(*p4, cx, cy, angle)
    rfill = [_rotate_point(*p, cx, cy, angle) for p in fill_pts]

    # Glass fill
    glass_poly = Polygon(rfill, facecolor="#AED6F1", edgecolor="none", alpha=0.5, zorder=3)
    ax.add_patch(glass_poly)

    # Double lines
    ax.plot([rp1[0], rp2[0]], [rp1[1], rp2[1]], color=WINDOW_COLOR, lw=WINDOW_LW, solid_capstyle="round", zorder=4)
    ax.plot([rp3[0], rp4[0]], [rp3[1], rp4[1]], color=WINDOW_COLOR, lw=1.2, solid_capstyle="round", zorder=4)

    # Ventilation marker for small windows
    if wtype == "ventilation":
        mid = _rotate_point(wx + ww / 2, wy + gap / 2, cx, cy, angle)
        ax.plot(*mid, "x", color=WINDOW_COLOR, ms=3, mew=1, zorder=5)


def _draw_north_arrow(ax, x: float, y: float, size: float = 4.0):
    """Decorative North arrow compass"""
    # Arrow body
    ax.annotate(
        "", xy=(x, y + size), xytext=(x, y),
        arrowprops=dict(arrowstyle="->", color=COMPASS_RED, lw=2.5),
        zorder=10
    )
    ax.text(x, y + size + 0.8, "N", ha="center", va="bottom",
            fontsize=12, fontweight="bold", color=COMPASS_RED, zorder=10)
    # Small circle at base
    circle = plt.Circle((x, y), 0.5, color=COMPASS_RED, fill=True, zorder=10)
    ax.add_patch(circle)


def _draw_dimension(ax, x1, y1, x2, y2, value_str: str,
                    offset: float = 2.5, color: str = DIM_COLOR):
    """Dimension line with arrows at ends"""
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 0.1:
        return

    # Perpendicular direction for offset
    nx, ny = -dy / length, dx / length
    ox, oy = nx * offset, ny * offset

    # Extension lines
    ax.plot([x1, x1 + ox], [y1, y1 + oy], color=color, lw=0.8, zorder=6)
    ax.plot([x2, x2 + ox], [y2, y2 + oy], color=color, lw=0.8, zorder=6)

    # Dimension line with arrows
    ax.annotate(
        "", xy=(x2 + ox, y2 + oy), xytext=(x1 + ox, y1 + oy),
        arrowprops=dict(arrowstyle="<->", color=color, lw=1.0),
        zorder=6
    )

    # Text
    ax.text(
        mx + ox * 1.2, my + oy * 1.2, value_str,
        ha="center", va="center",
        fontsize=FONT_DIM["size"],
        color=color,
        bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.8),
        zorder=7
    )


def _draw_plot_border(ax, length: float, breadth: float, cx: float, cy: float, angle: float):
    """Plot boundary — thick outer wall"""
    corners = _rect_corners(0, 0, length, breadth)
    rot = _rotate_corners(corners, cx, cy, angle)
    border = Polygon(rot, closed=True, facecolor="none",
                     edgecolor="#1a1a2e", linewidth=5, zorder=1)
    ax.add_patch(border)


def _draw_legend(ax, rooms: List[Dict]):
    """Compact room type legend"""
    seen_types = {}
    for r in rooms:
        t = r.get("type", "")
        if t not in seen_types:
            seen_types[t] = r.get("color", "#ccc")

    legend_handles = [
        mpatches.Patch(facecolor=col, edgecolor=WALL_COLOR, label=t.replace("_", " ").title())
        for t, col in seen_types.items()
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower left",
        fontsize=7,
        framealpha=0.9,
        edgecolor="#cccccc",
        title="Room Types",
        title_fontsize=7,
    )


# ─────────────────────────────────────────────────────────────────
# Main Renderer
# ─────────────────────────────────────────────────────────────────

def render_floor_plan(
    length: float,
    breadth: float,
    rooms: List[Dict],
    facing: str,
    bhk: str,
    show_dimensions: bool = True,
    show_vastu_overlay: bool = False,
    fig_w: float = 14,
    fig_h: float = 10,
) -> plt.Figure:
    """
    Complete floor plan render karo.

    Args:
        length, breadth : plot size in feet
        rooms           : list of room dicts from layout_engine
        facing          : "North" | "East" | "South" | "West"
        bhk             : BHK label for title
        show_dimensions : dimension lines show karo?
        show_vastu_overlay: Vastu zone grid show karo?

    Returns:
        matplotlib Figure
    """
    FACING_ANGLE = {"North": 0.0, "East": 90.0, "South": 180.0, "West": 270.0}
    angle = FACING_ANGLE[facing]
    cx, cy = length / 2, breadth / 2

    # ── Figure Setup ──────────────────────────────────────────────
    fig = plt.figure(figsize=(fig_w, fig_h), facecolor=BG_COLOR)
    gs  = GridSpec(1, 1, figure=fig, left=0.08, right=0.92, top=0.88, bottom=0.08)
    ax  = fig.add_subplot(gs[0, 0])

    ax.set_facecolor(BG_COLOR)
    ax.set_xlim(-4, length + 8)
    ax.set_ylim(-4, breadth + 8)
    ax.set_aspect("equal")
    ax.grid(True, color=GRID_COLOR, linestyle="--", linewidth=0.5, alpha=0.6, zorder=0)

    # ── Vastu Zone Overlay (optional) ─────────────────────────────
    if show_vastu_overlay:
        zw, zh = length / 3, breadth / 3
        zone_labels = [
            ("SW", 0, 0), ("S", 1, 0), ("SE", 2, 0),
            ("W", 0, 1),  ("C", 1, 1), ("E", 2, 1),
            ("NW", 0, 2), ("N", 1, 2), ("NE", 2, 2),
        ]
        for zlabel, col, row in zone_labels:
            zx, zy = col * zw, row * zh
            c = _rotate_corners(_rect_corners(zx, zy, zw, zh), cx, cy, angle)
            zpoly = Polygon(c, facecolor="#fffde7", edgecolor="#fbc02d",
                            linewidth=0.8, alpha=0.3, linestyle=":", zorder=1)
            ax.add_patch(zpoly)
            zcx = sum(p[0] for p in c) / 4
            zcy = sum(p[1] for p in c) / 4
            ax.text(zcx, zcy, zlabel, ha="center", va="center",
                    fontsize=7, color="#f57f17", alpha=0.6, style="italic")

    # ── Plot Border ───────────────────────────────────────────────
    _draw_plot_border(ax, length, breadth, cx, cy, angle)

    # ── Draw Rooms ────────────────────────────────────────────────
    for room in rooms:
        _draw_room(ax, room, cx, cy, angle, WALL_LW)

    # ── Draw Windows (under doors) ────────────────────────────────
    for room in rooms:
        for window in room.get("windows", []):
            _draw_window(ax, window, room, cx, cy, angle)

    # ── Draw Doors ────────────────────────────────────────────────
    for room in rooms:
        for door in room.get("doors", []):
            _draw_door(ax, door, room, cx, cy, angle)

    # ── Dimension Lines ───────────────────────────────────────────
    if show_dimensions:
        # Plot overall dimensions
        c_tl = _rotate_point(0, 0, cx, cy, angle)
        c_tr = _rotate_point(length, 0, cx, cy, angle)
        c_bl = _rotate_point(0, breadth, cx, cy, angle)

        _draw_dimension(ax, c_tl[0], c_tl[1], c_tr[0], c_tr[1],
                        f"{length:.0f} ft", offset=-3.0)
        _draw_dimension(ax, c_tl[0], c_tl[1], c_bl[0], c_bl[1],
                        f"{breadth:.0f} ft", offset=-3.0)

        # Individual room width labels
        for room in rooms:
            if room["type"] in ("living", "master_bed", "bedroom"):
                rx0, ry0 = _rotate_point(room["x"], room["y"], cx, cy, angle)
                rx1, ry1 = _rotate_point(room["x"] + room["w"], room["y"], cx, cy, angle)
                _draw_dimension(ax, rx0, ry0, rx1, ry1,
                                f'{room["w"]:.0f}\'', offset=0.8, color="#888888")

    # ── North Arrow ───────────────────────────────────────────────
    # Always top-right, no rotation needed for compass
    _draw_north_arrow(ax, length + 5, breadth - 6)

    # ── Vastu Score Panel ─────────────────────────────────────────
    vastu_audit  = audit_layout(rooms, length, breadth)
    vastu_overall = overall_vastu_score(vastu_audit)
    score_color   = "#27AE60" if vastu_overall >= 0.7 else "#F39C12" if vastu_overall >= 0.4 else "#E74C3C"

    score_text = f"Vastu Score: {vastu_overall * 100:.0f}%"
    ax.text(
        length + 1, breadth + 3, score_text,
        fontsize=9, color=score_color, fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                  edgecolor=score_color, linewidth=1.5, alpha=0.92),
        zorder=10
    )

    # ── Legend ────────────────────────────────────────────────────
    _draw_legend(ax, rooms)

    # ── Title & Subtitle ──────────────────────────────────────────
    total_area = length * breadth
    title_str    = f"Modern {bhk} Floor Plan  •  {facing} Facing"
    subtitle_str = f"Plot: {length:.0f} × {breadth:.0f} ft  |  Total Area: {total_area:.0f} sq ft  |  Scale: 1:50 approx"

    fig.text(0.5, 0.94, title_str,
             ha="center", va="center",
             fontsize=FONT_TITLE["size"],
             fontweight=FONT_TITLE["weight"],
             color="#1a1a2e")
    fig.text(0.5, 0.91, subtitle_str,
             ha="center", va="center",
             fontsize=FONT_SUBTITLE["size"],
             color="#555555")

    # ── Axis Labels ───────────────────────────────────────────────
    ax.set_xlabel("Length (feet)", fontsize=8, color=DIM_COLOR)
    ax.set_ylabel("Breadth (feet)", fontsize=8, color=DIM_COLOR)
    ax.tick_params(labelsize=7, colors=DIM_COLOR)

    plt.tight_layout(rect=[0, 0, 1, 0.90])
    return fig


# ─────────────────────────────────────────────────────────────────
# Export Helpers
# ─────────────────────────────────────────────────────────────────

def figure_to_pdf_bytes(fig: plt.Figure, dpi: int = 200) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="pdf", dpi=dpi, bbox_inches="tight", facecolor=BG_COLOR)
    buf.seek(0)
    return buf.getvalue()


def figure_to_png_bytes(fig: plt.Figure, dpi: int = 150) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor=BG_COLOR)
    buf.seek(0)
    return buf.getvalue()


def figure_to_svg_bytes(fig: plt.Figure) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", facecolor=BG_COLOR)
    buf.seek(0)
    return buf.getvalue()
