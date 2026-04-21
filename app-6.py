"""
app.py — Smart House Floor Plan Generator
==========================================
Streamlit-based professional UI.
Modern design + Vastu rules + Dynamic layout engine.
"""

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import sys, os

# Local modules
from layout_engine import create_layout
from renderer import (
    render_floor_plan,
    figure_to_pdf_bytes,
    figure_to_png_bytes,
    figure_to_svg_bytes,
)
from vastu import audit_layout, overall_vastu_score, VASTU_RULES


# ─────────────────────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="🏠 Smart House Plan Generator",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+Devanagari:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Noto Sans Devanagari', sans-serif;
    }
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1a1a2e;
        text-align: center;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1rem;
        color: #555;
        text-align: center;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background: #f8f9fa;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
    .vastu-ideal   { color: #27AE60; font-weight: bold; }
    .vastu-accept  { color: #F39C12; font-weight: bold; }
    .vastu-avoid   { color: #E74C3C; font-weight: bold; }
    .stButton > button {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 0.6rem 1.5rem;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 15px rgba(26,26,46,0.3);
    }
    .export-section {
        background: #f0f4ff;
        border-radius: 10px;
        padding: 1rem;
        margin-top: 1rem;
    }
    div[data-testid="stExpander"] {
        border: 1px solid #e0e0e0;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Header
# ─────────────────────────────────────────────────────────────────

st.markdown('<div class="main-title">🏠 Smart House Floor Plan Generator</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Vastu + Modern Design • Dynamic Layout • 1BHK to 4BHK • Export PDF / PNG / SVG</div>', unsafe_allow_html=True)
st.divider()


# ─────────────────────────────────────────────────────────────────
# Sidebar — Inputs
# ─────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 📐 Plot Details")

    col_a, col_b = st.columns(2)
    with col_a:
        length = st.number_input("लंबाई (ft)", min_value=15.0, max_value=200.0,
                                  value=45.0, step=1.0, help="Plot की लंबाई feet में")
    with col_b:
        breadth = st.number_input("चौड़ाई (ft)", min_value=15.0, max_value=150.0,
                                   value=35.0, step=1.0, help="Plot की चौड़ाई feet में")

    total_area = length * breadth
    st.caption(f"📏 कुल क्षेत्रफल: **{total_area:.0f} sq ft** ({total_area / 9:.0f} sq yards)")

    st.markdown("---")
    st.markdown("### 🏡 Design Options")

    bhk = st.selectbox(
        "BHK Type",
        ["1 BHK", "2 BHK", "3 BHK", "4 BHK"],
        index=1,
        help="कितने Bedroom चाहिए?"
    )

    facing = st.selectbox(
        "🧭 मकान की दिशा (Facing)",
        ["North", "East", "South", "West"],
        index=0,
        format_func=lambda x: {
            "North": "🔵 उत्तर (North) — सर्वोत्तम",
            "East":  "🟡 पूर्व (East) — शुभ",
            "South": "🔴 दक्षिण (South)",
            "West":  "⚪ पश्चिम (West)",
        }[x]
    )

    st.markdown("---")
    st.markdown("### ⚙️ Additional Options")

    modern_style   = st.checkbox("✨ Open Concept Modern Design", value=True,
                                  help="Open kitchen + Living merge करेगा")
    include_balcony = st.checkbox("🌿 Balcony शामिल करें", value=True)
    include_pooja   = st.checkbox("🪔 Pooja Room शामिल करें", value=True,
                                   help="2BHK+ ke liye")
    show_dimensions = st.checkbox("📏 Dimensions दिखाएं", value=True)
    show_vastu_zones = st.checkbox("🟨 Vastu Zone Grid दिखाएं", value=False)

    st.markdown("---")
    generate_btn = st.button("🚀 नक्शा बनाओ", type="primary", use_container_width=True)


# ─────────────────────────────────────────────────────────────────
# Session State
# ─────────────────────────────────────────────────────────────────

if "layout"  not in st.session_state: st.session_state.layout  = None
if "fig"     not in st.session_state: st.session_state.fig     = None
if "rooms"   not in st.session_state: st.session_state.rooms   = None


# ─────────────────────────────────────────────────────────────────
# Generate Layout
# ─────────────────────────────────────────────────────────────────

if generate_btn:
    with st.spinner("🔄 Layout engine calculate हो रही है..."):
        try:
            rooms = create_layout(
                length=length,
                breadth=breadth,
                bhk=bhk,
                facing=facing,
                modern_style=modern_style,
                include_balcony=include_balcony,
                include_pooja=include_pooja,
            )
            st.session_state.rooms = rooms

            fig = render_floor_plan(
                length=length,
                breadth=breadth,
                rooms=rooms,
                facing=facing,
                bhk=bhk,
                show_dimensions=show_dimensions,
                show_vastu_overlay=show_vastu_zones,
            )
            st.session_state.fig = fig
            plt.close("all")

            st.success("✅ नक्शा तैयार है!")
        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.exception(e)


# ─────────────────────────────────────────────────────────────────
# Main Output
# ─────────────────────────────────────────────────────────────────

if st.session_state.fig is not None and st.session_state.rooms is not None:
    rooms  = st.session_state.rooms
    fig    = st.session_state.fig

    # ── Floor Plan Display ────────────────────────────────────────
    col_plan, col_info = st.columns([2.2, 1])

    with col_plan:
        st.markdown("#### 📋 Generated Floor Plan")
        st.pyplot(fig, use_container_width=True)

    with col_info:
        # ── Room Summary ──────────────────────────────────────────
        st.markdown("#### 🏘️ Room Summary")

        total_room_area = sum(r["w"] * r["h"] for r in rooms)
        covered_pct = (total_room_area / (length * breadth)) * 100

        m1, m2 = st.columns(2)
        m1.metric("Total Rooms", len(rooms))
        m2.metric("Coverage", f"{covered_pct:.0f}%")

        st.markdown("---")
        for room in rooms:
            area = room["w"] * room["h"]
            dims = f'{room["w"]:.0f}×{room["h"]:.0f}'
            icon_map = {
                "living":   "🛋️", "bedroom":  "🛏️",
                "kitchen":  "🍳", "bathroom": "🚿",
                "balcony":  "🌿", "pooja":    "🪔",
                "dining":   "🍽️", "passage":  "🚪",
            }
            icon = icon_map.get(room.get("type", ""), "🔲")
            st.markdown(
                f"{icon} **{room['label']}**  \n"
                f"<small>{dims} ft • {area:.0f} sq ft</small>",
                unsafe_allow_html=True
            )
            st.markdown("")

        # ── Vastu Audit ───────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### 🧿 Vastu Report")

        vastu_audit   = audit_layout(rooms, length, breadth)
        overall_score = overall_vastu_score(vastu_audit)
        score_pct     = int(overall_score * 100)

        bar_color = "green" if score_pct >= 70 else "orange" if score_pct >= 40 else "red"
        st.progress(overall_score, text=f"Overall Vastu Score: {score_pct}%")

        with st.expander("🔍 Detailed Vastu Analysis"):
            for room_label, vscore in vastu_audit.items():
                status_icon = {"ideal": "✅", "acceptable": "⚠️", "avoid": "❌", "neutral": "➖"}
                icon = status_icon.get(vscore.status, "➖")
                css_class = {"ideal": "vastu-ideal", "acceptable": "vastu-accept", "avoid": "vastu-avoid"}.get(vscore.status, "")
                st.markdown(
                    f"{icon} **{room_label}** — Zone: `{vscore.zone}`  \n"
                    f"<small class='{css_class}'>{vscore.message}</small>",
                    unsafe_allow_html=True
                )
                st.markdown("")

    # ── Export Section ────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### 📤 Export Floor Plan")

    with st.container():
        exp_col1, exp_col2, exp_col3, exp_col4 = st.columns(4)

        with exp_col1:
            pdf_bytes = figure_to_pdf_bytes(fig, dpi=200)
            st.download_button(
                "📄 PDF Download",
                data=pdf_bytes,
                file_name=f"{bhk.replace(' ', '_')}_{facing}_{int(length)}x{int(breadth)}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )

        with exp_col2:
            png_bytes = figure_to_png_bytes(fig, dpi=150)
            st.download_button(
                "🖼️ PNG Download",
                data=png_bytes,
                file_name=f"{bhk.replace(' ', '_')}_{facing}_{int(length)}x{int(breadth)}.png",
                mime="image/png",
                use_container_width=True,
            )

        with exp_col3:
            svg_bytes = figure_to_svg_bytes(fig)
            st.download_button(
                "🎨 SVG Download",
                data=svg_bytes,
                file_name=f"{bhk.replace(' ', '_')}_{facing}_{int(length)}x{int(breadth)}.svg",
                mime="image/svg+xml",
                use_container_width=True,
            )

        with exp_col4:
            import json
            json_data = json.dumps(rooms, indent=2, ensure_ascii=False)
            st.download_button(
                "📊 JSON Data",
                data=json_data.encode("utf-8"),
                file_name=f"layout_{bhk.replace(' ','_')}.json",
                mime="application/json",
                use_container_width=True,
            )

    # ── Design Notes ──────────────────────────────────────────────
    with st.expander("📝 Design Notes & Vastu Tips"):
        st.markdown(f"""
**Plot:** {length:.0f} × {breadth:.0f} feet &nbsp;|&nbsp; **BHK:** {bhk} &nbsp;|&nbsp; **Facing:** {facing}

**Vastu Highlights applied:**
- 🟢 Living Room → North/East zone में (energy flow)
- 🟢 Kitchen → South-East zone में (Agni tatva)
- 🟢 Master Bedroom → South-West zone में (stability)
- 🟢 Pooja Room → North-East (Ishaan kon) में
- 🟡 Bathrooms → North-West/West side में

**Modern Design Features:**
{"- ✅ Open concept: Kitchen + Living merged" if modern_style else "- Separate Kitchen"}
{"- ✅ Balcony included on front/East side" if include_balcony else ""}
{"- ✅ Pooja room in NE corner" if include_pooja else ""}
- ✅ Attached bathrooms with bedrooms
- ✅ Passage/corridor for circulation

**Pro Tips:**
> Plot size {length:.0f}×{breadth:.0f} = {length*breadth:.0f} sq ft  
> For Indian urban plots, 60-70% coverage is ideal.  
> Current coverage: {covered_pct:.0f}%
        """)

else:
    # ── Welcome Screen ────────────────────────────────────────────
    st.markdown("""
    <div style="text-align:center; padding: 3rem; color: #888;">
        <div style="font-size: 5rem">🏠</div>
        <h3 style="color: #555">बाईं तरफ details भरें और <br>"नक्शा बनाओ" बटन दबाएं</h3>
        <p>✅ Vastu-based Dynamic Layout<br>
           ✅ 1BHK to 4BHK Support<br>
           ✅ PDF / PNG / SVG Export<br>
           ✅ Doors & Windows Auto-placement</p>
    </div>
    """, unsafe_allow_html=True)

    # Feature cards
    f1, f2, f3 = st.columns(3)
    with f1:
        st.info("🧭 **Vastu Rules**\n\nKitchen SE, Bedroom SW, Pooja NE — automatically follow होते हैं")
    with f2:
        st.info("⚡ **Dynamic Engine**\n\nHardcoded नहीं! Geometry-based placement — हर plot unique layout पाता है")
    with f3:
        st.info("📐 **Professional Output**\n\nArchitectural symbols, dimensions, north arrow, legend सब included")
