"""
layout_engine.py — Dynamic Geometry-Based Floor Plan Layout Engine
===================================================================
Ye file har cheez dynamically calculate karti hai — plot proportions,
room counts, Vastu zones, space allocation — kuch bhi hardcoded nahi hai.

Core Logic:
  1. Plot ko Vastu zones mein divide karo (3×3 grid)
  2. Har room type ka area proportion plot size se derive karo
  3. Rooms ko Vastu-preferred zones mein pack karo (bin-packing inspired)
  4. Doors & windows walls pe intelligently place karo
  5. Circulation paths ensure karo (rooms accessible hone chahiye)
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from shapely.geometry import box as shapely_box, Polygon as SPolygon
from shapely.ops import unary_union
import numpy as np

from vastu import get_preferred_position, VASTU_RULES


# ─────────────────────────────────────────────────────────────────
# Data Structures
# ─────────────────────────────────────────────────────────────────

@dataclass
class RoomSpec:
    """Ek room ki definition — type, size constraints, priority"""
    room_id:     str
    label:       str
    room_type:   str          # "bedroom", "living", "kitchen", etc.
    vastu_type:  str          # key for vastu.py rules
    area_ratio:  float        # fraction of total plot area
    min_w:       float        # minimum width (feet)
    min_h:       float        # minimum height (feet)
    aspect_min:  float = 0.6  # min w/h ratio
    aspect_max:  float = 2.5  # max w/h ratio
    priority:    int   = 5    # 1=highest, 10=lowest (placed first if high)
    color:       str   = "#f0f0f0"
    attached_bath: bool = False


@dataclass
class PlacedRoom:
    """Plot pe actually placed room ka rectangle + metadata"""
    room_id:    str
    label:      str
    type:       str
    vastu_type: str
    x:          float
    y:          float
    w:          float
    h:          float
    color:      str
    doors:      List[Dict]  = field(default_factory=list)
    windows:    List[Dict]  = field(default_factory=list)
    attached_bath: bool = False

    @property
    def cx(self) -> float: return self.x + self.w / 2
    @property
    def cy(self) -> float: return self.y + self.h / 2
    @property
    def area(self) -> float: return self.w * self.h
    @property
    def bounds(self) -> Tuple: return (self.x, self.y, self.x + self.w, self.y + self.h)

    def to_dict(self) -> Dict:
        return {
            "room_id": self.room_id, "label": self.label,
            "type": self.type, "vastu_type": self.vastu_type,
            "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "color": self.color, "doors": self.doors, "windows": self.windows,
            "attached_bath": self.attached_bath,
        }


# ─────────────────────────────────────────────────────────────────
# BHK Configuration Factory
# ─────────────────────────────────────────────────────────────────

ROOM_COLORS = {
    "living":   "#D6EAF8",   # soft blue
    "kitchen":  "#FEF9E7",   # warm cream
    "dining":   "#FDEBD0",   # peach
    "bedroom":  "#F9EBEA",   # soft rose
    "bathroom": "#D5F5E3",   # mint green
    "balcony":  "#FEF5E7",   # light amber
    "pooja":    "#F8F3FF",   # lavender
    "passage":  "#F2F3F4",   # neutral grey
    "staircase":"#E8DAEF",   # soft purple
}


def build_room_specs(bhk: str, plot_area: float, modern_style: bool,
                     include_balcony: bool, include_pooja: bool) -> List[RoomSpec]:
    """
    BHK type aur plot area se dynamically room specifications banao.
    Area ratios plot size ke saath scale karte hain.
    """
    specs: List[RoomSpec] = []

    # ── Living Room ──────────────────────────────────────────────
    living_ratio = 0.20 if bhk == "1 BHK" else 0.18 if bhk == "2 BHK" else 0.15
    specs.append(RoomSpec(
        room_id="living", label="Living Room",
        room_type="living", vastu_type="living",
        area_ratio=living_ratio, min_w=10, min_h=10,
        aspect_min=0.8, aspect_max=2.2,
        priority=1, color=ROOM_COLORS["living"]
    ))

    # ── Kitchen ──────────────────────────────────────────────────
    kitchen_label = "Open Kitchen" if modern_style else "Kitchen"
    specs.append(RoomSpec(
        room_id="kitchen", label=kitchen_label,
        room_type="kitchen", vastu_type="kitchen",
        area_ratio=0.10 if bhk == "1 BHK" else 0.09,
        min_w=8, min_h=7,
        aspect_min=0.7, aspect_max=2.0,
        priority=2, color=ROOM_COLORS["kitchen"]
    ))

    # ── Dining (2BHK+) ───────────────────────────────────────────
    if bhk in ["2 BHK", "3 BHK", "4 BHK"] and not modern_style:
        specs.append(RoomSpec(
            room_id="dining", label="Dining Area",
            room_type="dining", vastu_type="dining",
            area_ratio=0.08, min_w=8, min_h=7,
            priority=3, color=ROOM_COLORS["dining"]
        ))

    # ── Master Bedroom ───────────────────────────────────────────
    specs.append(RoomSpec(
        room_id="master_bed", label="Master Bedroom",
        room_type="bedroom", vastu_type="master_bedroom",
        area_ratio=0.16 if bhk == "1 BHK" else 0.14,
        min_w=10, min_h=10,
        aspect_min=0.7, aspect_max=1.8,
        priority=2, color=ROOM_COLORS["bedroom"],
        attached_bath=True
    ))

    # ── Additional Bedrooms ──────────────────────────────────────
    bed_count = {"1 BHK": 0, "2 BHK": 1, "3 BHK": 2, "4 BHK": 3}[bhk]
    bed_area_ratio = max(0.11 - (bed_count * 0.005), 0.09)

    for i in range(1, bed_count + 1):
        specs.append(RoomSpec(
            room_id=f"bed_{i}", label=f"Bedroom {i + 1}",
            room_type="bedroom", vastu_type="bedroom",
            area_ratio=bed_area_ratio,
            min_w=9, min_h=9,
            aspect_min=0.7, aspect_max=1.8,
            priority=3, color=ROOM_COLORS["bedroom"],
            attached_bath=(i == 1 and bhk in ["3 BHK", "4 BHK"])
        ))

    # ── Bathrooms ────────────────────────────────────────────────
    bath_count = {"1 BHK": 1, "2 BHK": 2, "3 BHK": 2, "4 BHK": 3}[bhk]
    for i in range(bath_count):
        specs.append(RoomSpec(
            room_id=f"bath_{i}", label=f"Bathroom {i + 1}",
            room_type="bathroom", vastu_type="bathroom",
            area_ratio=0.04, min_w=5, min_h=5,
            aspect_min=0.5, aspect_max=1.8,
            priority=6, color=ROOM_COLORS["bathroom"]
        ))

    # ── Pooja Room ───────────────────────────────────────────────
    if include_pooja and bhk in ["2 BHK", "3 BHK", "4 BHK"]:
        specs.append(RoomSpec(
            room_id="pooja", label="Pooja Room",
            room_type="pooja", vastu_type="pooja",
            area_ratio=0.03, min_w=5, min_h=5,
            aspect_min=0.6, aspect_max=1.5,
            priority=4, color=ROOM_COLORS["pooja"]
        ))

    # ── Balcony ──────────────────────────────────────────────────
    if include_balcony:
        specs.append(RoomSpec(
            room_id="balcony", label="Balcony",
            room_type="balcony", vastu_type="balcony",
            area_ratio=0.04, min_w=6, min_h=4,
            aspect_min=1.2, aspect_max=4.0,
            priority=7, color=ROOM_COLORS["balcony"]
        ))

    # ── Passage / Corridor ───────────────────────────────────────
    specs.append(RoomSpec(
        room_id="passage", label="Passage",
        room_type="passage", vastu_type="entrance",
        area_ratio=0.04, min_w=4, min_h=8,
        aspect_min=0.2, aspect_max=0.6,
        priority=8, color=ROOM_COLORS["passage"]
    ))

    return specs


# ─────────────────────────────────────────────────────────────────
# Geometry Placement Engine
# ─────────────────────────────────────────────────────────────────

WALL_THICKNESS = 0.5   # feet
MARGIN = 1.0           # outer boundary margin


class LayoutEngine:
    """
    Main layout engine — plot ke andar rooms ko intelligently place karta hai.

    Algorithm:
    1. Plot ko 3×3 Vastu zones mein divide karo
    2. Har spec ke liye target zone identify karo
    3. Zone mein available space check karo
    4. Room dimensions calculate karo (area ratio se)
    5. Collision-free placement ensure karo
    6. Doors aur windows place karo
    """

    def __init__(self, length: float, breadth: float):
        self.L = length
        self.B = breadth
        self.area = length * breadth
        self.placed: List[PlacedRoom] = []
        self._occupied_shapely: List = []

        # Available space tracking (per zone)
        self._zone_fill: Dict[str, float] = {}

    # ── Zone Helpers ──────────────────────────────────────────────

    def _zone_bounds(self, zone: str) -> Tuple[float, float, float, float]:
        """Zone name se uski boundary coordinates nikalo"""
        col_map = {"W": 0, "C": 1, "E": 2,
                   "SW": 0, "S": 1, "SE": 2,
                   "NW": 0, "N": 1, "NE": 2}
        row_map = {"SW": 0, "S": 0, "SE": 0,
                   "W":  1, "C": 1, "E":  1,
                   "NW": 2, "N": 2, "NE": 2}
        if len(zone) == 1:
            col_map_1 = {"W": 0, "C": 1, "E": 2}
            row_map_1 = {"S": 0, "C": 1, "N": 2}
            col = col_map_1.get(zone, 1)
            row = row_map_1.get(zone, 1)
        else:
            col = col_map.get(zone, 1)
            row = row_map.get(zone, 1)

        zw = self.L / 3
        zh = self.B / 3
        x0 = col * zw + MARGIN
        y0 = row * zh + MARGIN
        x1 = (col + 1) * zw - MARGIN
        y1 = (row + 1) * zh - MARGIN
        return (x0, y0, max(x0 + 1, x1), max(y0 + 1, y1))

    # ── Dimension Calculator ──────────────────────────────────────

    def _calc_dimensions(self, spec: RoomSpec) -> Tuple[float, float]:
        """
        Room ka target area calculate karo plot se,
        phir aspect ratio constraints ke andar width/height nikalo.
        """
        target_area = spec.area_ratio * self.area
        target_area = max(target_area, spec.min_w * spec.min_h)

        # Ideal aspect ratio — roughly 4:3 for rooms
        ideal_aspect = min(max(1.25, spec.aspect_min), spec.aspect_max)

        w = math.sqrt(target_area * ideal_aspect)
        h = target_area / w

        # Enforce minimums
        w = max(w, spec.min_w)
        h = max(h, spec.min_h)

        # Enforce plot boundary
        w = min(w, self.L - 2 * MARGIN)
        h = min(h, self.B - 2 * MARGIN)

        return round(w, 2), round(h, 2)

    # ── Collision Detection ───────────────────────────────────────

    def _overlaps(self, x: float, y: float, w: float, h: float,
                  gap: float = WALL_THICKNESS) -> bool:
        """Naya rectangle existing rooms se overlap karta hai?"""
        new_box = shapely_box(x - gap, y - gap, x + w + gap, y + h + gap)
        for occupied in self._occupied_shapely:
            if new_box.intersects(occupied):
                return True
        return False

    def _in_bounds(self, x: float, y: float, w: float, h: float) -> bool:
        return (x >= 0 and y >= 0 and
                x + w <= self.L and y + h <= self.B)

    # ── Smart Placement ───────────────────────────────────────────

    def _try_place_in_zone(self, zone: str, w: float, h: float,
                           step: float = 1.0) -> Optional[Tuple[float, float]]:
        """
        Zone ke andar collision-free position dhundo.
        Grid scan approach — step size se iterate karo.
        """
        x0, y0, x1, y1 = self._zone_bounds(zone)

        # Try zone ke andar multiple positions
        x = x0
        while x + w <= x1 + (self.L / 3):  # allow slight overflow into adjacent zone
            y = y0
            while y + h <= y1 + (self.B / 3):
                if self._in_bounds(x, y, w, h) and not self._overlaps(x, y, w, h):
                    return (x, y)
                y += step
            x += step
        return None

    def _try_place_anywhere(self, w: float, h: float,
                            step: float = 0.5) -> Optional[Tuple[float, float]]:
        """
        Agar preferred zone mein jagah nahi mili, toh pure plot scan karo.
        """
        x = MARGIN
        while x + w <= self.L - MARGIN:
            y = MARGIN
            while y + h <= self.B - MARGIN:
                if not self._overlaps(x, y, w, h):
                    return (x, y)
                y += step
            x += step
        return None

    # ── Door & Window Placement ───────────────────────────────────

    def _add_doors_windows(self, room: PlacedRoom, facing: str):
        """
        Room type ke hisaab se doors aur windows place karo.
        - Main entrance: facing direction ki wall pe
        - Bedrooms: corridor ki taraf door
        - Windows: outer walls pe prefer karo
        """
        doors = []
        windows = []

        facing_wall = {
            "North": "top", "South": "bottom",
            "East":  "right", "West": "left"
        }[facing]

        r_type = room.type

        # ── Doors ──
        if r_type == "living":
            # Main door — facing wall ke centre mein
            if facing_wall in ("bottom", "top"):
                dy = room.y if facing_wall == "bottom" else room.y + room.h
                doors.append({
                    "wall": facing_wall,
                    "x": room.cx - 1.5,
                    "y": dy,
                    "width": 3.0,
                    "type": "main"
                })
            else:
                dx = room.x if facing_wall == "left" else room.x + room.w
                doors.append({
                    "wall": facing_wall,
                    "x": dx,
                    "y": room.cy - 1.5,
                    "width": 3.0,
                    "type": "main"
                })
        elif r_type == "bedroom":
            # Bedroom door — room ke ek side mein
            doors.append({
                "wall": "bottom",
                "x": room.x + room.w * 0.15,
                "y": room.y,
                "width": 2.5,
                "type": "internal"
            })
        elif r_type == "kitchen":
            doors.append({
                "wall": "left",
                "x": room.x,
                "y": room.cy - 1.2,
                "width": 2.4,
                "type": "internal"
            })
        elif r_type == "bathroom":
            doors.append({
                "wall": "left" if room.w >= room.h else "bottom",
                "x": room.x if room.w >= room.h else room.cx - 1.0,
                "y": room.cy - 1.0 if room.w >= room.h else room.y,
                "width": 2.0,
                "type": "bathroom"
            })

        # ── Windows ──
        if r_type in ("living", "bedroom"):
            # Outer wall par window
            windows.append({
                "wall": "top",
                "x": room.x + room.w * 0.25,
                "y": room.y + room.h,
                "width": room.w * 0.35,
                "type": "casement"
            })
            if room.w > 14:
                windows.append({
                    "wall": "top",
                    "x": room.x + room.w * 0.65,
                    "y": room.y + room.h,
                    "width": room.w * 0.20,
                    "type": "casement"
                })
        if r_type == "kitchen":
            windows.append({
                "wall": "top",
                "x": room.cx - 1.5,
                "y": room.y + room.h,
                "width": 3.0,
                "type": "ventilation"
            })
        if r_type == "bathroom":
            windows.append({
                "wall": "top",
                "x": room.cx - 0.75,
                "y": room.y + room.h,
                "width": 1.5,
                "type": "ventilation"
            })

        room.doors = doors
        room.windows = windows

    # ── Attached Bathroom Placement ───────────────────────────────

    def _attach_bathroom(self, bedroom: PlacedRoom) -> Optional[PlacedRoom]:
        """
        Bedroom ke saath attached bathroom banao — bedroom se touch karke.
        """
        bw = max(5.0, bedroom.w * 0.30)
        bh = max(5.0, bedroom.h * 0.40)

        # Try right side, then top, then left
        candidates = [
            (bedroom.x + bedroom.w, bedroom.y + bedroom.h - bh),   # right
            (bedroom.x + bedroom.w - bw, bedroom.y + bedroom.h),   # top
            (bedroom.x - bw, bedroom.y + bedroom.h - bh),          # left
        ]
        for cx, cy in candidates:
            if self._in_bounds(cx, cy, bw, bh) and not self._overlaps(cx, cy, bw, bh):
                bath = PlacedRoom(
                    room_id=f"bath_att_{bedroom.room_id}",
                    label=f"Attached Bath",
                    type="bathroom", vastu_type="bathroom",
                    x=cx, y=cy, w=bw, h=bh,
                    color=ROOM_COLORS["bathroom"],
                    attached_bath=False
                )
                self._occupied_shapely.append(shapely_box(cx, cy, cx + bw, cy + bh))
                return bath
        return None

    # ── Main Entry Point ──────────────────────────────────────────

    def _facing_adjusted_zones(self, vastu_type: str, facing: str) -> List[str]:
        """
        Facing direction ke hisaab se preferred zones adjust karo.
        North facing = entrance N side pe, living bhi N/NE zone mein.
        """
        prefs     = VASTU_RULES.get(vastu_type, {}).get("preferred", ["C"])
        acceptable = VASTU_RULES.get(vastu_type, {}).get("acceptable", [])

        # Facing-based zone rotation mapping
        rotation_map = {
            "North": {},  # default — no rotation
            "East":  {"N": "E", "NE": "SE", "E": "S", "SE": "SW",
                      "S": "W", "SW": "NW", "W": "N", "NW": "NE"},
            "South": {"N": "S", "NE": "SW", "E": "W", "SE": "NW",
                      "S": "N", "SW": "NE", "W": "E", "NW": "SE"},
            "West":  {"N": "W", "NE": "NW", "E": "N", "SE": "NE",
                      "S": "E", "SW": "SE", "W": "S", "NW": "SW"},
        }
        rmap = rotation_map.get(facing, {})

        def rot(z): return rmap.get(z, z)

        rotated_prefs     = [rot(z) for z in prefs]
        rotated_acceptable = [rot(z) for z in acceptable]

        # All fallback zones (exclude forbidden)
        forbidden = VASTU_RULES.get(vastu_type, {}).get("forbidden", [])
        all_zones_ordered = (
            rotated_prefs + rotated_acceptable +
            [z for z in ["N", "NE", "E", "SE", "S", "SW", "W", "NW", "C"]
             if z not in rotated_prefs and z not in rotated_acceptable
             and rot(z) not in [rot(f) for f in forbidden]]
        )
        return all_zones_ordered

    def generate(self, specs: List[RoomSpec], facing: str) -> List[PlacedRoom]:
        """
        Saare specs ko place karo aur PlacedRoom list return karo.
        Facing-adjusted Vastu zones use karta hai.
        """
        sorted_specs = sorted(specs, key=lambda s: s.priority)

        for spec in sorted_specs:
            w, h = self._calc_dimensions(spec)

            all_zones = self._facing_adjusted_zones(spec.vastu_type, facing)

            placed_pos = None
            for zone in all_zones:
                placed_pos = self._try_place_in_zone(zone, w, h)
                if placed_pos:
                    break

            if not placed_pos:
                placed_pos = self._try_place_anywhere(w, h)

            if not placed_pos:
                placed_pos = (MARGIN, MARGIN)

            x, y = placed_pos
            room = PlacedRoom(
                room_id=spec.room_id, label=spec.label,
                type=spec.room_type, vastu_type=spec.vastu_type,
                x=round(x, 2), y=round(y, 2),
                w=round(w, 2), h=round(h, 2),
                color=spec.color,
                attached_bath=spec.attached_bath
            )

            self._add_doors_windows(room, facing)
            self.placed.append(room)
            self._occupied_shapely.append(shapely_box(x, y, x + w, y + h))

            # Attached bathrooms
            if spec.attached_bath:
                bath = self._attach_bathroom(room)
                if bath:
                    self._add_doors_windows(bath, facing)
                    self.placed.append(bath)

        return self.placed


# ─────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────

def create_layout(
    length: float,
    breadth: float,
    bhk: str,
    facing: str = "North",
    modern_style: bool = True,
    include_balcony: bool = True,
    include_pooja: bool = True,
) -> List[Dict]:
    """
    Main public function — layout generate karo aur dict list return karo.

    Returns:
        List of room dicts with keys:
        room_id, label, type, vastu_type, x, y, w, h, color, doors, windows
    """
    plot_area = length * breadth
    specs = build_room_specs(bhk, plot_area, modern_style, include_balcony, include_pooja)

    engine = LayoutEngine(length, breadth)
    placed_rooms = engine.generate(specs, facing)

    return [room.to_dict() for room in placed_rooms]
