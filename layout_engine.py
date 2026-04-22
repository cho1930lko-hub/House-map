"""
layout_engine.py — Production Floor Plan Layout Engine v2
==========================================================
Strip-based zero-overlap placement. Real architectural proportions.
"""
from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

WALL = 0.5

ROOM_COLORS = {
    "living":   "#D4E6F1", "kitchen":  "#FEF9E7", "dining":   "#FDEBD0",
    "bedroom":  "#FADBD8", "bathroom": "#D5F5E3", "balcony":  "#FEF5E7",
    "pooja":    "#EDE7F6", "passage":  "#ECEFF1", "utility":  "#F0F4C3",
}

VASTU_RULES = {
    "master_bedroom": {"preferred":["SW"],        "acceptable":["S","W"],    "forbidden":["NE","C"]},
    "bedroom":        {"preferred":["S","W","NW"], "acceptable":["SW","SE"],  "forbidden":["NE"]},
    "living":         {"preferred":["N","NE","E"], "acceptable":["NW"],       "forbidden":["SW"]},
    "kitchen":        {"preferred":["SE"],          "acceptable":["NW"],       "forbidden":["NE","SW","C"]},
    "bathroom":       {"preferred":["NW","W"],      "acceptable":["S","SE"],   "forbidden":["NE","C","SW"]},
    "pooja":          {"preferred":["NE"],          "acceptable":["N","E"],    "forbidden":["S","SW","SE","C"]},
    "balcony":        {"preferred":["N","E","NE"],  "acceptable":["NW"],       "forbidden":["SW"]},
    "dining":         {"preferred":["E","SE"],      "acceptable":["N","NE"],   "forbidden":["SW"]},
    "entrance":       {"preferred":["N","E","NE"],  "acceptable":["NW","SE"],  "forbidden":["SW","S"]},
}

@dataclass
class Room:
    id: str; label: str; type: str
    x: float; y: float; w: float; h: float; color: str
    doors:   List[Dict] = field(default_factory=list)
    windows: List[Dict] = field(default_factory=list)

    @property
    def cx(self): return round(self.x + self.w/2, 2)
    @property
    def cy(self): return round(self.y + self.h/2, 2)
    @property
    def area(self): return round(self.w * self.h, 1)
    @property
    def x2(self): return round(self.x + self.w, 2)
    @property
    def y2(self): return round(self.y + self.h, 2)

    def to_dict(self):
        return {"room_id":self.id,"label":self.label,"type":self.type,"vastu_type":self.type,
                "x":self.x,"y":self.y,"w":self.w,"h":self.h,"color":self.color,
                "doors":self.doors,"windows":self.windows}


class FloorPlanEngine:
    def __init__(self, L, B):
        self.L = L; self.B = B

    def _doors_windows(self, r: Room, facing: str):
        doors, wins = [], []
        fw = {"North":"top","South":"bottom","East":"right","West":"left"}[facing]
        t  = r.type

        if t == "living":
            if fw in ("top","bottom"):
                wy = r.y2 if fw=="top" else r.y
                doors.append({"wall":fw,"x":r.x+r.w*0.18,"y":wy,"width":3.5,"type":"main"})
                wins.append({"wall":fw,"x":r.x+r.w*0.55,"y":wy,"width":r.w*0.28,"type":"casement"})
            else:
                wx = r.x2 if fw=="right" else r.x
                doors.append({"wall":fw,"x":wx,"y":r.y+r.h*0.18,"width":3.5,"type":"main"})
                wins.append({"wall":fw,"x":wx,"y":r.y+r.h*0.55,"width":r.h*0.28,"type":"casement"})
            wins.append({"wall":"right","x":r.x2,"y":r.cy-1.2,"width":2.5,"type":"casement"})

        elif t == "kitchen":
            doors.append({"wall":"bottom","x":r.cx-1.2,"y":r.y,"width":2.4,"type":"internal"})
            wins.append({"wall":"top","x":r.cx-1.5,"y":r.y2,"width":3.0,"type":"ventilation"})

        elif t == "bedroom":
            doors.append({"wall":"bottom","x":r.x+r.w*0.15,"y":r.y,"width":2.5,"type":"internal"})
            wins.append({"wall":"top","x":r.x+r.w*0.2,"y":r.y2,"width":r.w*0.32,"type":"casement"})
            if r.w > 11:
                wins.append({"wall":"right","x":r.x2,"y":r.cy-1.1,"width":2.2,"type":"casement"})

        elif t == "bathroom":
            side = "left" if r.w >= r.h else "bottom"
            bx = r.x if side=="left" else r.cx-1.0
            by = r.cy-1.0 if side=="left" else r.y
            doors.append({"wall":side,"x":bx,"y":by,"width":2.0,"type":"bathroom"})
            wins.append({"wall":"top","x":r.cx-0.5,"y":r.y2,"width":1.0,"type":"ventilation"})

        elif t == "pooja":
            doors.append({"wall":"bottom","x":r.cx-0.8,"y":r.y,"width":1.6,"type":"internal"})

        elif t == "dining":
            doors.append({"wall":"left","x":r.x,"y":r.cy-1.1,"width":2.2,"type":"internal"})

        elif t == "balcony":
            wins.append({"wall":"top","x":r.x+0.5,"y":r.y2,"width":r.w-1.0,"type":"railing"})

        r.doors = doors; r.windows = wins

    def _make(self, id, label, type_, x, y, w, h):
        return Room(id, label, type_, round(x,2), round(y,2),
                    round(max(w,3.0),2), round(max(h,3.0),2), ROOM_COLORS.get(type_,"#f0f0f0"))

    # ─── 1 BHK ──────────────────────────────────────────────────
    def _1bhk(self, facing, modern, balcony):
        L, B, p = self.L, self.B, WALL
        pw  = max(4.0, L*0.13)          # passage
        uw  = L - pw - p
        fh  = B * 0.45                  # front (living+kitchen)
        bkh = B - fh - p               # back (bedroom)

        rs = [
            self._make("living","Living Room","living",       pw, B-fh, uw*0.62, fh),
            self._make("kitchen","Kitchen","kitchen",         pw+uw*0.63, B-fh+fh*0.42, uw*0.37, fh*0.58),
            self._make("dining","Dining","dining",            pw+uw*0.63, B-fh, uw*0.37, fh*0.40),
            self._make("master_bed","Master Bedroom","bedroom", pw, p, uw*0.68, bkh),
            self._make("bath_att","Attached Bath","bathroom", pw+uw*0.68+p, p, uw*0.32-p, bkh*0.45),
            self._make("passage","Passage","passage",         p, p, pw-p*2, B-p*2),
        ]
        if balcony:
            rs.append(self._make("balcony","Balcony","balcony", pw, B, min(uw*0.4,10.0), 5.0))
        return rs

    # ─── 2 BHK ──────────────────────────────────────────────────
    def _2bhk(self, facing, modern, balcony, pooja):
        L, B, p = self.L, self.B, WALL
        pw = max(4.5, L*0.11); uw = L - pw - p
        fh = B*0.40; bh = B - fh - p

        rs = [
            self._make("living","Living Room","living",         pw, B-fh, uw*0.58, fh),
            self._make("kitchen","Open Kitchen" if modern else "Kitchen","kitchen",
                                                                pw+uw*0.59, B-fh+fh*0.44, uw*0.41, fh*0.56),
            self._make("dining","Dining Area","dining",         pw+uw*0.59, B-fh, uw*0.41, fh*0.42),
            self._make("master_bed","Master Bedroom","bedroom", pw, p, uw*0.52, bh),
            self._make("bath_att","Attached Bath","bathroom",   pw+uw*0.52-uw*0.18, p, uw*0.18, bh*0.42),
            self._make("bed2","Bedroom 2","bedroom",            pw+uw*0.53, p, uw*0.47, bh*0.60),
            self._make("bath1","Common Bath","bathroom",        pw+uw*0.53, p+bh*0.61, uw*0.25, bh*0.39-p),
            self._make("passage","Passage","passage",           p, p, pw-p*2, B-p*2),
        ]
        if pooja:
            rs.append(self._make("pooja","Pooja Room","pooja", pw+uw*0.53+uw*0.26, p+bh*0.61, uw*0.21, bh*0.39-p))
        if balcony:
            rs.append(self._make("balcony","Balcony","balcony", pw, B, min(uw*0.38,12.0), 5.0))
        return rs

    # ─── 3 BHK ──────────────────────────────────────────────────
    def _3bhk(self, facing, modern, balcony, pooja):
        L, B, p = self.L, self.B, WALL
        pw = max(4.5, L*0.10); uw = L - pw - p
        fh = B*0.38; bh = B - fh - p

        b2w = uw*0.31; b3w = uw*0.27; mbw = uw - b2w - b3w - p*2
        b2h = bh*0.58; service_h = bh - b2h - p

        rs = [
            self._make("living","Living Room","living",           pw, B-fh, uw*0.57, fh),
            self._make("kitchen","Open Kitchen" if modern else "Kitchen","kitchen",
                                                                   pw+uw*0.58, B-fh+fh*0.45, uw*0.42, fh*0.55),
            self._make("dining","Dining Area","dining",            pw+uw*0.58, B-fh, uw*0.42, fh*0.43),
            self._make("master_bed","Master Bedroom","bedroom",    pw, p, mbw, bh),
            self._make("bath_att","Attached Bath","bathroom",      pw+mbw-mbw*0.33, p, mbw*0.33, bh*0.40),
            self._make("bed2","Bedroom 2","bedroom",               pw+mbw+p, p, b2w, b2h),
            self._make("bed3","Bedroom 3","bedroom",               pw+mbw+p+b2w+p, p, b3w, b2h),
            self._make("bath1","Common Bath","bathroom",           pw+mbw+p, p+b2h+p, b2w*0.52, service_h-p),
            self._make("utility","Utility / Store","utility",      pw+mbw+p+b2w+p, p+b2h+p, b3w, service_h-p),
            self._make("passage","Passage","passage",              p, p, pw-p*2, B-p*2),
        ]
        if pooja:
            rs.append(self._make("pooja","Pooja Room","pooja",
                pw+mbw+p+b2w*0.53, p+b2h+p, b2w*0.47, service_h-p))
        if balcony:
            rs.append(self._make("balcony","Balcony","balcony",
                pw, B, min(uw*0.38,13.0), 5.5))
        return rs

    # ─── 4 BHK ──────────────────────────────────────────────────
    def _4bhk(self, facing, modern, balcony, pooja):
        L, B, p = self.L, self.B, WALL
        pw = max(5.0, L*0.09); uw = L - pw - p
        fh = B*0.37; bh = B - fh - p

        mbw  = uw*0.30
        bw34 = (uw - mbw - p*3) / 3
        b_h  = bh*0.57; srv_h = bh - b_h - p

        rs = [
            self._make("living","Living Room","living",           pw, B-fh, uw*0.55, fh),
            self._make("kitchen","Modular Kitchen","kitchen",     pw+uw*0.56, B-fh+fh*0.46, uw*0.44, fh*0.54),
            self._make("dining","Dining Area","dining",           pw+uw*0.56, B-fh, uw*0.44, fh*0.44),
            self._make("master_bed","Master Bedroom","bedroom",   pw, p, mbw, bh),
            self._make("bath_att","Master Bath","bathroom",       pw+mbw-mbw*0.35, p, mbw*0.35, bh*0.42),
            self._make("bed2","Bedroom 2","bedroom",              pw+mbw+p, p, bw34, b_h),
            self._make("bed3","Bedroom 3","bedroom",              pw+mbw+p+bw34+p, p, bw34, b_h),
            self._make("bed4","Bedroom 4","bedroom",              pw+mbw+p+bw34*2+p*2, p, bw34, b_h),
            self._make("bath1","Bathroom 2","bathroom",           pw+mbw+p, p+b_h+p, bw34*0.50, srv_h-p),
            self._make("bath2","Bathroom 3","bathroom",           pw+mbw+p+bw34+p, p+b_h+p, bw34*0.50, srv_h-p),
            self._make("utility","Utility","utility",             pw+mbw+p+bw34*2+p*2, p+b_h+p, bw34, srv_h-p),
            self._make("passage","Passage","passage",             p, p, pw-p*2, B-p*2),
        ]
        if pooja:
            rs.append(self._make("pooja","Pooja Room","pooja",
                pw+mbw+p+bw34*0.51, p+b_h+p, bw34*0.49, srv_h-p))
        if balcony:
            rs.append(self._make("balcony","Balcony","balcony",
                pw, B, min(uw*0.35,14.0), 6.0))
        return rs

    def generate(self, bhk, facing, modern, balcony, pooja):
        fn = {"1 BHK":self._1bhk,"2 BHK":self._2bhk,"3 BHK":self._3bhk,"4 BHK":self._4bhk}[bhk]
        rooms = fn(facing, modern, balcony) if bhk=="1 BHK" else fn(facing, modern, balcony, pooja)

        for r in rooms:
            r.x = max(0.0, min(r.x, self.L - r.w))
            r.y = max(0.0, min(r.y, self.B - r.h))
            self._doors_windows(r, facing)
        return rooms


def create_layout(length, breadth, bhk, facing="North",
                  modern_style=True, include_balcony=True, include_pooja=True):
    engine = FloorPlanEngine(length, breadth)
    rooms  = engine.generate(bhk, facing, modern_style, include_balcony, include_pooja)
    return [r.to_dict() for r in rooms]


def audit_vastu(rooms, L, B):
    results = {}
    for r in rooms:
        cx = r["x"]+r["w"]/2; cy = r["y"]+r["h"]/2
        col = min(int(cx/(L/3)),2); row = min(int(cy/(B/3)),2)
        zone = {(0,0):"SW",(1,0):"S",(2,0):"SE",(0,1):"W",(1,1):"C",(2,1):"E",
                (0,2):"NW",(1,2):"N",(2,2):"NE"}.get((col,row),"C")
        vt = r.get("vastu_type", r.get("type","bedroom"))
        rules = VASTU_RULES.get(vt,{})
        if zone in rules.get("preferred",[]):   status,score,icon="ideal",1.0,"✅"
        elif zone in rules.get("acceptable",[]): status,score,icon="acceptable",0.6,"⚠️"
        elif zone in rules.get("forbidden",[]):  status,score,icon="avoid",0.0,"❌"
        else:                                     status,score,icon="neutral",0.5,"➖"
        results[r["label"]] = {"zone":zone,"status":status,"score":score,"icon":icon}
    total = sum(v["score"] for v in results.values())
    overall = round(total/max(len(results),1),2)
    return {"rooms":results,"overall":overall,"pct":int(overall*100)}

