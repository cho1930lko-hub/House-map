"""
vastu.py — Vastu Shastra Rule Engine
=====================================
Vastu principles ke according room placement constraints define karta hai.
Har room ke liye preferred zones, forbidden zones, aur scoring system.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ─────────────────────────────────────────────
# Compass & Zone Definitions
# ─────────────────────────────────────────────

FACING_ROTATION: Dict[str, float] = {
    "North":  0.0,
    "East":   90.0,
    "South":  180.0,
    "West":   270.0,
}

# 9-zone grid (3x3) — Vastu Purush Mandala inspired
# Each zone is (col, row) where (0,0) = bottom-left = South-West
ZONE_NAMES = {
    (0, 0): "SW",  (1, 0): "S",  (2, 0): "SE",
    (0, 1): "W",   (1, 1): "C",  (2, 1): "E",
    (0, 2): "NW",  (1, 2): "N",  (2, 2): "NE",
}

# Vastu ideal zones per room type
VASTU_RULES: Dict[str, Dict] = {
    "master_bedroom": {
        "preferred":  ["SW"],
        "acceptable": ["S", "W"],
        "forbidden":  ["NE", "C"],
        "reason":     "Master bedroom SW mein sab se shubh maana jaata hai (stability & rest)",
    },
    "bedroom": {
        "preferred":  ["S", "W", "NW"],
        "acceptable": ["SW", "SE"],
        "forbidden":  ["NE"],
        "reason":     "Bedrooms S/W side mein aate hain",
    },
    "living": {
        "preferred":  ["N", "NE", "E"],
        "acceptable": ["NW"],
        "forbidden":  ["SW"],
        "reason":     "Living room ka mukh North/East ki taraf hona chahiye (energy flow)",
    },
    "kitchen": {
        "preferred":  ["SE"],
        "acceptable": ["NW"],
        "forbidden":  ["NE", "SW", "C"],
        "reason":     "Kitchen SE mein Agni tatva ke anusar sahi hai",
    },
    "bathroom": {
        "preferred":  ["NW", "W"],
        "acceptable": ["S", "SE"],
        "forbidden":  ["NE", "C", "SW"],
        "reason":     "Bathrooms NW ya W mein acceptable hain",
    },
    "pooja": {
        "preferred":  ["NE"],
        "acceptable": ["N", "E"],
        "forbidden":  ["S", "SW", "SE", "C"],
        "reason":     "Pooja room NE mein (Ishaan kon) sab se pavitra jagah hai",
    },
    "balcony": {
        "preferred":  ["N", "E", "NE"],
        "acceptable": ["NW"],
        "forbidden":  ["SW"],
        "reason":     "Balcony North/East side mein sunlight aur air ke liye ideal hai",
    },
    "dining": {
        "preferred":  ["E", "SE"],
        "acceptable": ["N", "NE"],
        "forbidden":  ["SW"],
        "reason":     "Dining E/SE mein ho toh khana khaate samay positive energy milti hai",
    },
    "staircase": {
        "preferred":  ["S", "SW", "W"],
        "acceptable": ["SE"],
        "forbidden":  ["NE", "C", "N"],
        "reason":     "Staircase SW/S mein stable maani jaati hai",
    },
    "entrance": {
        "preferred":  ["N", "E", "NE"],
        "acceptable": ["NW", "SE"],
        "forbidden":  ["SW", "S"],
        "reason":     "Main entrance N ya E ki taraf se shubh aur welcoming hoti hai",
    },
}


@dataclass
class VastuScore:
    zone: str
    score: float          # 0.0 – 1.0
    status: str           # "ideal" | "acceptable" | "avoid"
    message: str


def get_zone(x: float, y: float, length: float, breadth: float) -> str:
    """
    Room ke center coordinates se Vastu zone determine karo.
    Returns zone name like "NE", "SW", "C" etc.
    """
    col = min(int(x / (length / 3)), 2)
    row = min(int(y / (breadth / 3)), 2)
    return ZONE_NAMES.get((col, row), "C")


def score_placement(room_type: str, zone: str) -> VastuScore:
    """
    Ek room ko uske zone ke basis par Vastu score do.
    """
    rules = VASTU_RULES.get(room_type, {})
    if not rules:
        return VastuScore(zone=zone, score=0.5, status="neutral", message="No specific Vastu rule")

    if zone in rules.get("preferred", []):
        return VastuScore(
            zone=zone,
            score=1.0,
            status="ideal",
            message=f"✅ {rules['reason']}"
        )
    elif zone in rules.get("acceptable", []):
        return VastuScore(
            zone=zone,
            score=0.6,
            status="acceptable",
            message=f"⚠️ Acceptable but not ideal. {rules['reason']}"
        )
    elif zone in rules.get("forbidden", []):
        return VastuScore(
            zone=zone,
            score=0.0,
            status="avoid",
            message=f"❌ Vastu dosh! {rules['reason']}"
        )
    else:
        return VastuScore(zone=zone, score=0.4, status="neutral", message="Neutral zone")


def get_preferred_position(
    room_type: str,
    length: float,
    breadth: float,
    fallback_zone: str = "C"
) -> Tuple[float, float]:
    """
    Room type ke liye preferred Vastu zone ka center point return karo.
    Layout engine is position ko anchor point ki tarah use karta hai.
    """
    rules = VASTU_RULES.get(room_type, {})
    preferred = rules.get("preferred", [fallback_zone])
    target_zone = preferred[0]

    zone_to_coords = {
        "SW": (0.17, 0.17), "S": (0.50, 0.17), "SE": (0.83, 0.17),
        "W":  (0.17, 0.50), "C": (0.50, 0.50), "E":  (0.83, 0.50),
        "NW": (0.17, 0.83), "N": (0.50, 0.83), "NE": (0.83, 0.83),
    }
    rel = zone_to_coords.get(target_zone, (0.5, 0.5))
    return rel[0] * length, rel[1] * breadth


def audit_layout(layout: List[Dict], length: float, breadth: float) -> Dict[str, VastuScore]:
    """
    Poore layout ka Vastu audit karo.
    Returns: {room_label: VastuScore}
    """
    report = {}
    for room in layout:
        cx = room["x"] + room["w"] / 2
        cy = room["y"] + room["h"] / 2
        zone = get_zone(cx, cy, length, breadth)
        r_type = room.get("vastu_type", room.get("type", "bedroom"))
        score = score_placement(r_type, zone)
        report[room["label"]] = score
    return report


def overall_vastu_score(audit: Dict[str, VastuScore]) -> float:
    """
    Sabhi rooms ke scores ka weighted average.
    """
    if not audit:
        return 0.0
    weights = {"ideal": 1.0, "acceptable": 0.6, "neutral": 0.4, "avoid": 0.0}
    total = sum(weights.get(s.status, 0.4) for s in audit.values())
    return round(total / len(audit), 2)
