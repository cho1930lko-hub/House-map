"""
renderer.py — Professional Architectural Floor Plan Renderer v2
================================================================
Realistic walls, proper door arcs, window symbols, dimensions.
Clean architectural style — not a child's drawing.
"""
from __future__ import annotations
import math, io
from typing import Dict, List, Tuple
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon, Arc, FancyArrowPatch
from matplotlib.lines import Line2D

# ── Style Constants ──────────────────────────────────────────────
WALL_C   = "#1C2833"
WALL_LW  = 4.0
THIN_LW  = 1.5
DOOR_C   = "#784212"
WIN_C    = "#1A5276"
DIM_C    = "#626567"
GRID_C   = "#D5D8DC"
BG_C     = "#FDFEFE"
TEXT_C   = "#17202A"
NORTH_C  = "#C0392B"

def _rot(x, y, cx, cy, a):
    r = math.radians(a)
    dx, dy = x-cx, y-cy
    return cx+dx*math.cos(r)-dy*math.sin(r), cy+dx*math.sin(r)+dy*math.cos(r)

def _rot_corners(corners, cx, cy, a):
    return [_rot(x, y, cx, cy, a) for x,y in corners]

def _rect_pts(x,y,w,h):
    return [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]


# ── Room ─────────────────────────────────────────────────────────
def _draw_room(ax, r, cx, cy, angle):
    x,y,w,h = r["x"],r["y"],r["w"],r["h"]
    pts = _rot_corners(_rect_pts(x,y,w,h), cx, cy, angle)

    # Fill
    poly = Polygon(pts, closed=True, facecolor=r.get("color","#f0f0f0"),
                   edgecolor=WALL_C, lw=WALL_LW, alpha=0.90, zorder=2)
    ax.add_patch(poly)

    # Room label + area
    rcx = sum(p[0] for p in pts)/4
    rcy = sum(p[1] for p in pts)/4
    label = r.get("label","")
    area  = r["w"]*r["h"]

    # Icon per type
    icons = {"living":"⬛","bedroom":"⬛","kitchen":"⬛","bathroom":"⬛",
             "balcony":"⬛","pooja":"⬛","dining":"⬛","passage":"⬛","utility":"⬛"}

    ax.text(rcx, rcy+0.6, label, ha="center", va="center",
            fontsize=8.5, fontweight="bold", color=TEXT_C, zorder=6,
            bbox=dict(boxstyle="round,pad=0.15",facecolor="white",edgecolor="none",alpha=0.75))
    ax.text(rcx, rcy-0.9, f"{area:.0f} sq ft",
            ha="center", va="center", fontsize=6.5,
            color="#555", style="italic", zorder=6)


# ── Door ─────────────────────────────────────────────────────────
def _draw_door(ax, door, cx, cy, angle):
    wall  = door.get("wall","bottom")
    dx    = door.get("x", 0)
    dy    = door.get("y", 0)
    dw    = door.get("width", 3.0)
    dtype = door.get("type","internal")
    color = "#8B0000" if dtype=="main" else DOOR_C
    lw    = 2.8 if dtype=="main" else 1.8

    # Hinge point and end point based on wall
    if wall == "bottom":
        hx,hy = dx,dy;      ex,ey = dx+dw,dy
        a1,a2 = 0,90;       acx,acy = hx,hy
    elif wall == "top":
        hx,hy = dx,dy;      ex,ey = dx+dw,dy
        a1,a2 = 270,360;    acx,acy = hx,hy
    elif wall == "left":
        hx,hy = dx,dy;      ex,ey = dx,dy+dw
        a1,a2 = 0,90;       acx,acy = hx,hy
    else:  # right
        hx,hy = dx,dy;      ex,ey = dx,dy+dw
        a1,a2 = 90,180;     acx,acy = hx,hy

    rhx,rhy = _rot(hx,hy,cx,cy,angle)
    rex,rey = _rot(ex,ey,cx,cy,angle)
    rax,ray = _rot(acx,acy,cx,cy,angle)

    # Door panel
    ax.plot([rhx,rex],[rhy,rey], color=color, lw=lw,
            solid_capstyle="round", zorder=5)
    # Swing arc
    arc = Arc((rax,ray), dw*2, dw*2, angle=angle,
              theta1=a1, theta2=a2,
              color=color, lw=1.2, linestyle="--", zorder=5)
    ax.add_patch(arc)


# ── Window ───────────────────────────────────────────────────────
def _draw_window(ax, win, cx, cy, angle):
    wall = win.get("wall","top")
    wx   = win.get("x",0)
    wy   = win.get("y",0)
    ww   = win.get("width",3.0)
    g    = 0.4  # gap between double lines

    if wall in ("top","bottom"):
        p1,p2 = (wx,wy),(wx+ww,wy)
        p3,p4 = (wx,wy+g),(wx+ww,wy+g)
        fill  = [(wx,wy),(wx+ww,wy),(wx+ww,wy+g),(wx,wy+g)]
    else:
        p1,p2 = (wx,wy),(wx,wy+ww)
        p3,p4 = (wx+g,wy),(wx+g,wy+ww)
        fill  = [(wx,wy),(wx+g,wy),(wx+g,wy+ww),(wx,wy+ww)]

    rfill = [_rot(p[0],p[1],cx,cy,angle) for p in fill]
    rp1   = _rot(*p1,cx,cy,angle)
    rp2   = _rot(*p2,cx,cy,angle)
    rp3   = _rot(*p3,cx,cy,angle)
    rp4   = _rot(*p4,cx,cy,angle)

    glass = Polygon(rfill, facecolor="#AED6F1", edgecolor="none", alpha=0.55, zorder=4)
    ax.add_patch(glass)
    ax.plot([rp1[0],rp2[0]],[rp1[1],rp2[1]], color=WIN_C, lw=3.0,
            solid_capstyle="round", zorder=5)
    ax.plot([rp3[0],rp4[0]],[rp3[1],rp4[1]], color=WIN_C, lw=1.2,
            solid_capstyle="round", zorder=5)


# ── Dimension Line ───────────────────────────────────────────────
def _dim(ax, x1,y1,x2,y2, label, offset=2.8):
    mx,my = (x1+x2)/2,(y1+y2)/2
    dx,dy = x2-x1,y2-y1
    L     = math.hypot(dx,dy)
    if L < 0.1: return
    nx,ny = -dy/L*offset, dx/L*offset

    ax.plot([x1,x1+nx],[y1,y1+ny], color=DIM_C, lw=0.8, zorder=7)
    ax.plot([x2,x2+nx],[y2,y2+ny], color=DIM_C, lw=0.8, zorder=7)
    ax.annotate("",xy=(x2+nx,y2+ny),xytext=(x1+nx,y1+ny),
                arrowprops=dict(arrowstyle="<->",color=DIM_C,lw=1.0),zorder=7)
    ax.text(mx+nx*1.15,my+ny*1.15, label, ha="center", va="center",
            fontsize=6.5, color=DIM_C,
            bbox=dict(boxstyle="round,pad=0.12",facecolor="white",edgecolor="none",alpha=0.85),zorder=8)


# ── North Arrow ──────────────────────────────────────────────────
def _north_arrow(ax, x, y, size=3.5):
    ax.annotate("",xy=(x,y+size),xytext=(x,y),
                arrowprops=dict(arrowstyle="->",color=NORTH_C,lw=2.2),zorder=12)
    ax.text(x,y+size+0.7,"N",ha="center",va="bottom",
            fontsize=11,fontweight="bold",color=NORTH_C,zorder=12)
    ax.add_patch(plt.Circle((x,y),0.4,color=NORTH_C,zorder=12))


# ── Vastu Score Badge ────────────────────────────────────────────
def _vastu_badge(ax, score_pct, x, y):
    color = "#1E8449" if score_pct>=70 else "#D35400" if score_pct>=45 else "#C0392B"
    ax.text(x,y,f"Vastu {score_pct}%",fontsize=8.5,fontweight="bold",color=color,
            bbox=dict(boxstyle="round,pad=0.4",facecolor="white",
                      edgecolor=color,lw=1.8,alpha=0.95),zorder=12)


# ── Legend ───────────────────────────────────────────────────────
def _legend(ax, rooms):
    seen = {}
    for r in rooms:
        t = r.get("type","")
        if t not in seen: seen[t]=r.get("color","#ccc")
    handles = [mpatches.Patch(facecolor=c,edgecolor=WALL_C,
               label=t.replace("_"," ").title()) for t,c in seen.items()]
    ax.legend(handles=handles,loc="lower left",fontsize=6.5,
              framealpha=0.92,edgecolor="#bbb",
              title="Room Types",title_fontsize=6.5)


# ── Main Renderer ────────────────────────────────────────────────
def render_floor_plan(length, breadth, rooms, facing, bhk,
                      vastu_pct=0, show_dimensions=True,
                      show_vastu_grid=False, fig_w=15, fig_h=11):

    ANGLE = {"North":0,"East":90,"South":180,"West":270}[facing]
    cx, cy = length/2, breadth/2

    fig, ax = plt.subplots(figsize=(fig_w,fig_h))
    fig.patch.set_facecolor(BG_C)
    ax.set_facecolor(BG_C)
    ax.set_xlim(-5, length+10)
    ax.set_ylim(-5, breadth+10)
    ax.set_aspect("equal")
    ax.grid(True, color=GRID_C, ls="--", lw=0.4, alpha=0.55, zorder=0)

    # Vastu zone grid (optional)
    if show_vastu_grid:
        zw, zh = length/3, breadth/3
        for col in range(3):
            for row in range(3):
                pts = _rot_corners(_rect_pts(col*zw,row*zh,zw,zh),cx,cy,ANGLE)
                ax.add_patch(Polygon(pts,facecolor="#fffde7",edgecolor="#f9ca24",
                                     lw=0.6,alpha=0.25,linestyle=":",zorder=1))
                labels = {(0,0):"SW",(1,0):"S",(2,0):"SE",(0,1):"W",(1,1):"C",
                          (2,1):"E",(0,2):"NW",(1,2):"N",(2,2):"NE"}
                zcx = sum(p[0] for p in pts)/4
                zcy = sum(p[1] for p in pts)/4
                ax.text(zcx,zcy,labels[(col,row)],ha="center",va="center",
                        fontsize=7,color="#e67e22",alpha=0.6,style="italic")

    # Plot boundary — double line for outer wall
    border_pts = _rot_corners(_rect_pts(0,0,length,breadth),cx,cy,ANGLE)
    ax.add_patch(Polygon(border_pts,closed=True,facecolor="none",
                         edgecolor=WALL_C,lw=5.5,zorder=1))
    ax.add_patch(Polygon(border_pts,closed=True,facecolor="none",
                         edgecolor="#85929E",lw=1.5,linestyle="--",
                         zorder=1,alpha=0.4))

    # Rooms
    for r in rooms: _draw_room(ax, r, cx, cy, ANGLE)
    # Windows (under doors)
    for r in rooms:
        for w in r.get("windows",[]): _draw_window(ax, w, cx, cy, ANGLE)
    # Doors
    for r in rooms:
        for d in r.get("doors",[]): _draw_door(ax, d, cx, cy, ANGLE)

    # Dimensions
    if show_dimensions:
        c00 = _rot(0,0,cx,cy,ANGLE)
        c10 = _rot(length,0,cx,cy,ANGLE)
        c01 = _rot(0,breadth,cx,cy,ANGLE)
        _dim(ax,*c00,*c10, f"{length:.0f} ft", offset=-3.2)
        _dim(ax,*c00,*c01, f"{breadth:.0f} ft", offset=-3.2)

        for r in rooms:
            if r.get("type") in ("living","bedroom"):
                rx0,ry0 = _rot(r["x"],r["y"],cx,cy,ANGLE)
                rx1,ry1 = _rot(r["x"]+r["w"],r["y"],cx,cy,ANGLE)
                _dim(ax,rx0,ry0,rx1,ry1, f'{r["w"]:.0f}\'', offset=0.7)

    # North arrow + Vastu badge
    _north_arrow(ax, length+7, breadth-7)
    _vastu_badge(ax, vastu_pct, length+1, breadth+3)

    # Legend
    _legend(ax, rooms)

    # Title
    area = length*breadth
    fig.text(0.5, 0.95, f"Modern {bhk} Floor Plan  •  {facing} Facing",
             ha="center", fontsize=14, fontweight="bold", color="#1C2833")
    fig.text(0.5, 0.92,
             f"Plot: {length:.0f}×{breadth:.0f} ft  |  Area: {area:.0f} sq ft  |  Scale: 1:50",
             ha="center", fontsize=8.5, color="#555")

    ax.set_xlabel("Length (feet)", fontsize=7.5, color=DIM_C)
    ax.set_ylabel("Breadth (feet)", fontsize=7.5, color=DIM_C)
    ax.tick_params(labelsize=6.5, colors=DIM_C)
    plt.tight_layout(rect=[0,0,1,0.91])
    return fig


# ── Exports ──────────────────────────────────────────────────────
def to_pdf(fig, dpi=200):
    buf=io.BytesIO(); fig.savefig(buf,format="pdf",dpi=dpi,bbox_inches="tight",
                                   facecolor=BG_C); buf.seek(0); return buf.getvalue()

def to_png(fig, dpi=150):
    buf=io.BytesIO(); fig.savefig(buf,format="png",dpi=dpi,bbox_inches="tight",
                                   facecolor=BG_C); buf.seek(0); return buf.getvalue()

def to_svg(fig):
    buf=io.BytesIO(); fig.savefig(buf,format="svg",bbox_inches="tight",
                                   facecolor=BG_C); buf.seek(0); return buf.getvalue()
