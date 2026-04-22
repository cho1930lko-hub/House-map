"""
html_export.py — Interactive HTML Floor Plan Generator
=======================================================
SVG-based interactive floor plan with zoom, pan, room tooltips.
Standalone HTML file — works offline, no dependencies.
"""
from __future__ import annotations
from typing import Dict, List
import json, math

WALL_COLOR  = "#1C2833"
FONT_STACK  = "system-ui, -apple-system, 'Segoe UI', sans-serif"

def _hex_to_rgba(hex_color, alpha=0.88):
    h = hex_color.lstrip("#")
    r,g,b = int(h[0:2],16), int(h[2:4],16), int(h[4:6],16)
    return f"rgba({r},{g},{b},{alpha})"


def generate_html(length: float, breadth: float, rooms: List[Dict],
                  facing: str, bhk: str, vastu_pct: int,
                  password: str = "") -> str:
    """
    Complete standalone interactive HTML floor plan.
    Password protection optional.
    """
    # Scale: 1 foot = 14px
    SCALE = 14
    SVG_W = int(length * SCALE)
    SVG_H = int(breadth * SCALE)

    # Build SVG room elements
    svg_rooms = []
    for r in rooms:
        rx = r["x"] * SCALE
        # Flip Y axis (SVG top = 0, we want bottom = 0)
        ry = (breadth - r["y"] - r["h"]) * SCALE
        rw = r["w"] * SCALE
        rh = r["h"] * SCALE
        color = r.get("color","#f0f0f0")
        label = r.get("label","")
        area  = r["w"] * r["h"]
        rtype = r.get("type","")

        # Door SVG
        door_svg = ""
        for d in r.get("doors",[]):
            dw  = d.get("width",3.0) * SCALE
            wall = d.get("wall","bottom")
            dtype = d.get("type","internal")
            dc   = "#8B0000" if dtype=="main" else "#784212"
            lw   = 2.5 if dtype=="main" else 1.5

            ddx  = (d.get("x",r["x"]) - r["x"]) * SCALE
            ddy  = (d.get("y",r["y"]) - r["y"]) * SCALE

            if wall == "bottom":
                # Door on bottom → in flipped SVG = top of rect
                door_svg += f'''<line x1="{rx+ddx}" y1="{ry+rh}" x2="{rx+ddx+dw}" y2="{ry+rh}"
                    stroke="{dc}" stroke-width="{lw}" stroke-linecap="round"/>
                <path d="M{rx+ddx},{ry+rh} a{dw},{dw} 0 0,1 {dw},{-dw}"
                    fill="none" stroke="{dc}" stroke-width="1" stroke-dasharray="4,2"/>'''
            elif wall == "top":
                door_svg += f'''<line x1="{rx+ddx}" y1="{ry}" x2="{rx+ddx+dw}" y2="{ry}"
                    stroke="{dc}" stroke-width="{lw}" stroke-linecap="round"/>
                <path d="M{rx+ddx},{ry} a{dw},{dw} 0 0,0 {dw},{dw}"
                    fill="none" stroke="{dc}" stroke-width="1" stroke-dasharray="4,2"/>'''

        # Window SVG
        win_svg = ""
        for w in r.get("windows",[]):
            wall = w.get("wall","top")
            wwid = w.get("width",3.0) * SCALE
            wtype = w.get("type","casement")
            wdx  = (w.get("x",r["x"]) - r["x"]) * SCALE

            if wall in ("top","bottom"):
                wy = ry if wall=="top" else ry+rh
                win_svg += f'''<rect x="{rx+wdx}" y="{wy-3}" width="{wwid}" height="6"
                    fill="#AED6F1" fill-opacity="0.7" stroke="#1A5276" stroke-width="2"/>'''

        svg_rooms.append(f'''
        <g class="room" data-label="{label}" data-area="{area:.0f}" data-type="{rtype}">
            <rect x="{rx}" y="{ry}" width="{rw}" height="{rh}"
                fill="{color}" fill-opacity="0.88"
                stroke="{WALL_COLOR}" stroke-width="3"
                rx="1" ry="1"
                class="room-rect" data-label="{label}"/>
            {door_svg}
            {win_svg}
            <text x="{rx+rw/2}" y="{ry+rh/2-6}"
                text-anchor="middle" dominant-baseline="middle"
                font-family="{FONT_STACK}" font-size="11" font-weight="600"
                fill="{WALL_COLOR}">{label}</text>
            <text x="{rx+rw/2}" y="{ry+rh/2+10}"
                text-anchor="middle" dominant-baseline="middle"
                font-family="{FONT_STACK}" font-size="9" fill="#555"
                font-style="italic">{area:.0f} sq ft</text>
        </g>''')

    rooms_svg = "\n".join(svg_rooms)

    # Vastu color
    v_color = "#1E8449" if vastu_pct>=70 else "#D35400" if vastu_pct>=45 else "#C0392B"

    # Room list for sidebar
    room_list_html = ""
    type_icons = {
        "living":"🛋️","bedroom":"🛏️","kitchen":"🍳","bathroom":"🚿",
        "balcony":"🌿","pooja":"🪔","dining":"🍽️","passage":"🚶","utility":"🧹"
    }
    for r in rooms:
        icon = type_icons.get(r.get("type",""),"🔲")
        area = r["w"]*r["h"]
        room_list_html += f'''
        <div class="room-item" onclick="highlightRoom('{r['label']}')">
            <span class="room-icon">{icon}</span>
            <div class="room-info">
                <div class="room-name">{r['label']}</div>
                <div class="room-size">{r['w']:.0f}×{r['h']:.0f} ft &nbsp;|&nbsp; {area:.0f} sq ft</div>
            </div>
        </div>'''

    # Password protection JS
    pw_html  = ""
    pw_js    = ""
    pw_style = ""
    if password:
        pw_style = "#pw-screen{position:fixed;inset:0;background:#1a1a2e;display:flex;align-items:center;justify-content:center;z-index:9999;flex-direction:column;gap:1rem}.pw-box{background:#16213e;padding:2.5rem 3rem;border-radius:16px;border:1px solid #0f3460;text-align:center}.pw-box h2{color:#e0e0e0;margin-bottom:1.5rem;font-size:1.4rem}.pw-input{background:#0f3460;border:1px solid #4a90d9;color:white;padding:.75rem 1.2rem;border-radius:8px;font-size:1rem;width:220px;text-align:center;outline:none}.pw-btn{background:linear-gradient(135deg,#4a90d9,#1a6ea3);color:white;border:none;padding:.75rem 2rem;border-radius:8px;font-size:1rem;cursor:pointer;margin-top:.5rem;font-weight:600}.pw-err{color:#e74c3c;font-size:.85rem;display:none}"
        pw_html = f'''<div id="pw-screen">
            <div class="pw-box">
                <h2>🔐 Floor Plan — Secure Access</h2>
                <input type="password" id="pw-input" class="pw-input" placeholder="Enter Password" onkeydown="if(event.key==='Enter')checkPw()">
                <br><button class="pw-btn" onclick="checkPw()">Unlock</button>
                <p class="pw-err" id="pw-err">❌ Incorrect password</p>
            </div>
        </div>'''
        pw_js = f'''
        function checkPw(){{
            var v=document.getElementById('pw-input').value;
            if(v==='{password}'){{
                document.getElementById('pw-screen').style.display='none';
                localStorage.setItem('fp_auth','1');
            }} else {{
                document.getElementById('pw-err').style.display='block';
                document.getElementById('pw-input').value='';
            }}
        }}
        if(localStorage.getItem('fp_auth')==='1')
            document.getElementById('pw-screen').style.display='none';
        '''

    html = f'''<!DOCTYPE html>
<html lang="hi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>🏠 {bhk} Floor Plan — {facing} Facing</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:{FONT_STACK};background:#F4F6F7;color:#1C2833;overflow-x:hidden}}
{pw_style}

/* Header */
.header{{background:linear-gradient(135deg,#1C2833 0%,#2E4057 100%);color:white;
         padding:1.2rem 2rem;display:flex;align-items:center;justify-content:space-between;
         box-shadow:0 2px 12px rgba(0,0,0,0.3)}}
.header-title{{font-size:1.3rem;font-weight:700}}
.header-sub{{font-size:.8rem;opacity:.75;margin-top:.2rem}}
.vastu-badge{{background:white;color:{v_color};padding:.4rem .9rem;
              border-radius:20px;font-weight:700;font-size:.85rem;
              border:2px solid {v_color}}}

/* Layout */
.main{{display:flex;height:calc(100vh - 62px)}}
.sidebar{{width:280px;min-width:280px;background:white;
          border-right:1px solid #ddd;overflow-y:auto;
          display:flex;flex-direction:column}}
.sidebar-section{{padding:1rem;border-bottom:1px solid #eee}}
.sidebar-section h3{{font-size:.85rem;font-weight:700;color:#555;
                      text-transform:uppercase;letter-spacing:.05em;margin-bottom:.75rem}}
.room-item{{display:flex;align-items:center;gap:.7rem;padding:.55rem .75rem;
            border-radius:8px;cursor:pointer;transition:background .15s}}
.room-item:hover{{background:#f0f4ff}}
.room-icon{{font-size:1.2rem;width:28px;text-align:center}}
.room-name{{font-size:.85rem;font-weight:600;color:#1C2833}}
.room-size{{font-size:.75rem;color:#888}}

/* Controls */
.controls{{display:flex;gap:.5rem;padding:.75rem 1rem;flex-wrap:wrap;
           background:#f8f9fa;border-top:1px solid #eee;margin-top:auto}}
.ctrl-btn{{flex:1;min-width:60px;padding:.5rem;background:#1C2833;color:white;
           border:none;border-radius:6px;font-size:.78rem;cursor:pointer;
           font-weight:600;transition:all .15s}}
.ctrl-btn:hover{{background:#2E4057;transform:translateY(-1px)}}
.ctrl-btn.outline{{background:white;color:#1C2833;border:1.5px solid #1C2833}}
.ctrl-btn.outline:hover{{background:#f0f4ff}}

/* Canvas */
.canvas-wrap{{flex:1;overflow:hidden;position:relative;background:#FAFAFA}}
#svg-container{{width:100%;height:100%;overflow:auto;padding:30px}}
svg.floor-plan{{cursor:grab;user-select:none}}
svg.floor-plan:active{{cursor:grabbing}}

/* Room highlight */
.room-rect{{transition:filter .2s}}
.room-rect:hover{{filter:brightness(0.9);cursor:pointer}}
.room-rect.highlighted{{filter:brightness(0.85) drop-shadow(0 0 6px #2980B9)}}

/* Tooltip */
#tooltip{{position:fixed;background:#1C2833;color:white;padding:.5rem .9rem;
          border-radius:8px;font-size:.82rem;pointer-events:none;
          display:none;z-index:1000;box-shadow:0 4px 12px rgba(0,0,0,0.3)}}

/* Zoom controls */
.zoom-controls{{position:absolute;bottom:20px;right:20px;
                display:flex;flex-direction:column;gap:.4rem}}
.zoom-btn{{width:36px;height:36px;background:white;border:1.5px solid #ddd;
           border-radius:8px;font-size:1.1rem;cursor:pointer;
           display:flex;align-items:center;justify-content:center;
           box-shadow:0 2px 6px rgba(0,0,0,.1);transition:all .15s}}
.zoom-btn:hover{{background:#f0f4ff;border-color:#4a90d9}}

/* Scale bar */
.scale-bar{{position:absolute;bottom:20px;left:50%;transform:translateX(-50%);
            background:rgba(255,255,255,.95);border:1px solid #ddd;
            padding:.3rem .8rem;border-radius:6px;font-size:.75rem;color:#555}}

/* Responsive */
@media(max-width:768px){{
    .sidebar{{width:100%;min-width:unset;height:200px;border-right:none;border-bottom:1px solid #ddd}}
    .main{{flex-direction:column}}
}}
</style>
</head>
<body>
{pw_html}

<div class="header">
    <div>
        <div class="header-title">🏠 {bhk} Floor Plan &nbsp;•&nbsp; {facing} Facing</div>
        <div class="header-sub">Plot: {length:.0f}×{breadth:.0f} ft &nbsp;|&nbsp; {length*breadth:.0f} sq ft &nbsp;|&nbsp; Scale: 1:50</div>
    </div>
    <div class="vastu-badge">Vastu {vastu_pct}%</div>
</div>

<div id="tooltip"></div>

<div class="main">
    <!-- Sidebar -->
    <div class="sidebar">
        <div class="sidebar-section">
            <h3>Rooms</h3>
            {room_list_html}
        </div>
        <div class="controls">
            <button class="ctrl-btn" onclick="resetZoom()">⟳ Reset</button>
            <button class="ctrl-btn outline" onclick="zoomIn()">＋ Zoom</button>
            <button class="ctrl-btn outline" onclick="zoomOut()">－ Zoom</button>
        </div>
    </div>

    <!-- Floor Plan SVG -->
    <div class="canvas-wrap" id="canvas-wrap">
        <div id="svg-container">
            <svg class="floor-plan" id="fp-svg"
                 width="{SVG_W + 80}" height="{SVG_H + 80}"
                 viewBox="-40 -40 {SVG_W+80} {SVG_H+80}"
                 xmlns="http://www.w3.org/2000/svg">

                <!-- Background -->
                <rect x="-40" y="-40" width="{SVG_W+80}" height="{SVG_H+80}"
                      fill="#FAFAFA"/>
                <!-- Grid lines -->
                {''.join(f'<line x1="{i*SCALE}" y1="-40" x2="{i*SCALE}" y2="{SVG_H+40}" stroke="#E0E0E0" stroke-width="0.5"/>' for i in range(int(length)+2))}
                {''.join(f'<line x1="-40" y1="{i*SCALE}" x2="{SVG_W+40}" y2="{i*SCALE}" stroke="#E0E0E0" stroke-width="0.5"/>' for i in range(int(breadth)+2))}

                <!-- Plot outline -->
                <rect x="0" y="0" width="{SVG_W}" height="{SVG_H}"
                      fill="none" stroke="{WALL_COLOR}" stroke-width="5"/>

                <!-- Rooms -->
                {rooms_svg}

                <!-- North Arrow -->
                <g transform="translate({SVG_W+25}, 30)">
                    <line x1="0" y1="25" x2="0" y2="5"
                          stroke="#C0392B" stroke-width="2.5"
                          marker-end="url(#arrowhead)"/>
                    <circle cx="0" cy="28" r="5" fill="#C0392B"/>
                    <text x="0" y="-2" text-anchor="middle"
                          font-size="13" font-weight="bold" fill="#C0392B">N</text>
                </g>

                <!-- Scale bar -->
                <g transform="translate(10, {SVG_H+25})">
                    <line x1="0" y1="0" x2="{10*SCALE}" y2="0"
                          stroke="#555" stroke-width="2"/>
                    <line x1="0" y1="-4" x2="0" y2="4" stroke="#555" stroke-width="2"/>
                    <line x1="{10*SCALE}" y1="-4" x2="{10*SCALE}" y2="4" stroke="#555" stroke-width="2"/>
                    <text x="{5*SCALE}" y="14" text-anchor="middle"
                          font-size="10" fill="#555">10 feet</text>
                </g>

                <!-- Dimension labels -->
                <text x="{SVG_W/2}" y="{SVG_H+52}" text-anchor="middle"
                      font-size="11" fill="#666">{length:.0f} ft</text>
                <text x="-28" y="{SVG_H/2}" text-anchor="middle"
                      font-size="11" fill="#666"
                      transform="rotate(-90,-28,{SVG_H/2})">{breadth:.0f} ft</text>

                <!-- Arrow marker -->
                <defs>
                    <marker id="arrowhead" markerWidth="8" markerHeight="6"
                            refX="8" refY="3" orient="auto">
                        <polygon points="0 0, 8 3, 0 6" fill="#C0392B"/>
                    </marker>
                </defs>
            </svg>
        </div>

        <div class="zoom-controls">
            <button class="zoom-btn" onclick="zoomIn()" title="Zoom In">＋</button>
            <button class="zoom-btn" onclick="resetZoom()" title="Reset">⊙</button>
            <button class="zoom-btn" onclick="zoomOut()" title="Zoom Out">－</button>
        </div>
    </div>
</div>

<script>
{pw_js}

// ── Zoom & Pan ──────────────────────────────────────────────────
let scale=1, panX=0, panY=0, isDragging=false, startX=0, startY=0;
const svg = document.getElementById('fp-svg');
const cont = document.getElementById('svg-container');

function applyTransform(){{
    svg.style.transform = `translate(${{panX}}px, ${{panY}}px) scale(${{scale}})`;
    svg.style.transformOrigin = 'center center';
}}
function zoomIn(){{ scale=Math.min(scale*1.25, 5); applyTransform(); }}
function zoomOut(){{ scale=Math.max(scale/1.25, 0.3); applyTransform(); }}
function resetZoom(){{ scale=1; panX=0; panY=0; applyTransform(); }}

svg.addEventListener('wheel', e=>{{
    e.preventDefault();
    scale = e.deltaY<0 ? Math.min(scale*1.12,5) : Math.max(scale/1.12,0.3);
    applyTransform();
}}, {{passive:false}});

svg.addEventListener('mousedown', e=>{{
    isDragging=true; startX=e.clientX-panX; startY=e.clientY-panY;
    svg.classList.add('grabbing');
}});
document.addEventListener('mousemove', e=>{{
    if(!isDragging) return;
    panX=e.clientX-startX; panY=e.clientY-startY; applyTransform();
}});
document.addEventListener('mouseup', ()=>{{ isDragging=false; }});

// Touch support
let lastTouchDist=0;
svg.addEventListener('touchstart', e=>{{
    if(e.touches.length===2){{
        lastTouchDist=Math.hypot(
            e.touches[0].clientX-e.touches[1].clientX,
            e.touches[0].clientY-e.touches[1].clientY);
    }} else if(e.touches.length===1){{
        isDragging=true;
        startX=e.touches[0].clientX-panX;
        startY=e.touches[0].clientY-panY;
    }}
}},{{passive:true}});
svg.addEventListener('touchmove', e=>{{
    if(e.touches.length===2){{
        const d=Math.hypot(e.touches[0].clientX-e.touches[1].clientX,
                           e.touches[0].clientY-e.touches[1].clientY);
        scale=Math.min(Math.max(scale*(d/lastTouchDist),0.3),5);
        lastTouchDist=d; applyTransform();
    }} else if(isDragging && e.touches.length===1){{
        panX=e.touches[0].clientX-startX;
        panY=e.touches[0].clientY-startY; applyTransform();
    }}
}},{{passive:true}});
svg.addEventListener('touchend', ()=>isDragging=false);

// ── Tooltip & Highlight ─────────────────────────────────────────
const tip = document.getElementById('tooltip');
document.querySelectorAll('.room-rect').forEach(el=>{{
    el.addEventListener('mouseenter', e=>{{
        const label=el.dataset.label;
        tip.innerHTML=`<b>${{label}}</b>`;
        tip.style.display='block';
    }});
    el.addEventListener('mousemove', e=>{{
        tip.style.left=e.clientX+14+'px';
        tip.style.top=e.clientY-8+'px';
    }});
    el.addEventListener('mouseleave', ()=>tip.style.display='none');
}});

function highlightRoom(label){{
    document.querySelectorAll('.room-rect').forEach(el=>{{
        if(el.dataset.label===label){{
            el.classList.toggle('highlighted');
        }} else el.classList.remove('highlighted');
    }});
}}
</script>
</body>
</html>'''

    return html
