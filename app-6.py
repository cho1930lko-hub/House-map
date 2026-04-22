"""
app.py — Smart House Floor Plan Generator
==========================================
Professional Streamlit app with:
- Password protection
- Multi-AI suggestions (Groq + Gemini + DeepSeek)
- Interactive HTML export
- PDF export
- Parallel plan generation
"""

import streamlit as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import os, json, hashlib

from layout_engine import create_layout, audit_vastu
from renderer     import render_floor_plan, to_pdf, to_png, to_svg
from ai_engine    import get_ai_suggestions, generate_parallel_plans
from html_export  import generate_html

# ─────────────────────────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🏠 Smart Floor Plan Generator",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────
# Password Protection
# ─────────────────────────────────────────────────────────────────
APP_PASSWORD = os.environ.get("APP_PASSWORD", "")   # set in Streamlit secrets

def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()

if APP_PASSWORD:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        st.markdown("""
        <style>
        .pw-wrap{display:flex;align-items:center;justify-content:center;
                 height:80vh;flex-direction:column;gap:1.5rem}
        .pw-card{background:white;padding:3rem 3.5rem;border-radius:16px;
                 border:1px solid #e0e0e0;box-shadow:0 8px 30px rgba(0,0,0,.08);
                 text-align:center;min-width:360px}
        .pw-title{font-size:1.8rem;font-weight:700;margin-bottom:.5rem}
        .pw-sub{color:#888;font-size:.9rem;margin-bottom:2rem}
        </style>
        <div class="pw-wrap">
            <div class="pw-card">
                <div class="pw-title">🔐 Secure Access</div>
                <div class="pw-sub">Floor Plan Generator — Password Protected</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        pw_input = st.text_input("Password", type="password",
                                  placeholder="Enter access password",
                                  label_visibility="collapsed")
        col1,col2,col3 = st.columns([2,1,2])
        with col2:
            if st.button("🔓 Unlock", use_container_width=True, type="primary"):
                if _hash(pw_input) == _hash(APP_PASSWORD):
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Incorrect password")
        st.stop()


# ─────────────────────────────────────────────────────────────────
# Custom CSS — Professional Dark-Accented Theme
# ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html,body,[class*="css"]{font-family:'Inter',sans-serif}

.block-container{padding-top:1.5rem!important}

/* Sidebar */
[data-testid="stSidebar"]{background:#F8F9FA}
[data-testid="stSidebar"] .stSelectbox label,
[data-testid="stSidebar"] .stNumberInput label,
[data-testid="stSidebar"] .stCheckbox label{
    font-size:.83rem!important;font-weight:500;color:#444}

/* Metric cards */
.metric-row{display:flex;gap:1rem;margin-bottom:1rem}
.metric-card{flex:1;background:white;border:1px solid #e8ecf0;
             border-radius:10px;padding:1rem;text-align:center}
.metric-val{font-size:1.6rem;font-weight:700;color:#1C2833}
.metric-lbl{font-size:.75rem;color:#888;margin-top:.2rem}

/* Room table */
.room-row{display:flex;align-items:center;padding:.45rem .6rem;
          border-radius:6px;transition:background .12s}
.room-row:hover{background:#F0F4FF}
.room-label{font-size:.83rem;font-weight:600;flex:1}
.room-dims{font-size:.75rem;color:#888}

/* AI response cards */
.ai-card{background:white;border:1px solid #e8ecf0;border-radius:12px;
         padding:1.2rem;margin-bottom:1rem;
         border-left:4px solid var(--ai-color)}
.ai-header{display:flex;align-items:center;gap:.6rem;margin-bottom:.8rem}
.ai-name{font-weight:700;font-size:.9rem}
.ai-time{font-size:.72rem;color:#aaa;margin-left:auto}
.ai-body{font-size:.83rem;line-height:1.6;color:#333;white-space:pre-wrap}

/* Export buttons */
.export-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.75rem;
             margin-top:1rem}

/* Vastu progress */
.vastu-bar-wrap{margin:.5rem 0}

/* Tabs styling */
.stTabs [data-baseweb="tab"]{font-size:.85rem;font-weight:500}

/* Buttons */
.stButton>button{border-radius:8px!important;font-weight:600!important;
                 transition:all .15s!important}

/* Download buttons */
.stDownloadButton>button{border-radius:8px!important;font-weight:500!important}

/* Section header */
.section-head{font-size:1rem;font-weight:700;color:#1C2833;
              padding-bottom:.4rem;border-bottom:2px solid #E8ECF0;
              margin-bottom:.8rem}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────
# Session State Init
# ─────────────────────────────────────────────────────────────────
for k, v in [("rooms",None),("fig",None),("vastu",None),
             ("ai_results",None),("html_str",None)]:
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🏠 Floor Plan Settings")

    c1,c2 = st.columns(2)
    with c1: length  = st.number_input("Length (ft)",15.0,200.0,45.0,1.0)
    with c2: breadth = st.number_input("Breadth (ft)",15.0,150.0,35.0,1.0)

    area_sqft  = length*breadth
    area_sqyd  = area_sqft/9
    st.caption(f"📐 {area_sqft:.0f} sq ft  ({area_sqyd:.0f} sq yards)")

    st.divider()

    bhk    = st.selectbox("BHK Type", ["1 BHK","2 BHK","3 BHK","4 BHK"], index=1)
    facing = st.selectbox("Facing Direction",
                          ["North","East","South","West"],
                          format_func=lambda x:{
                              "North":"🔵 North (उत्तर) — Best",
                              "East" :"🟡 East (पूर्व) — Good",
                              "South":"🔴 South (दक्षिण)",
                              "West" :"⚪ West (पश्चिम)"}[x])

    st.divider()
    st.markdown("**Design Options**")
    modern  = st.checkbox("✨ Open Concept Modern",True)
    balcony = st.checkbox("🌿 Include Balcony",True)
    pooja   = st.checkbox("🪔 Pooja Room",True)

    st.divider()
    st.markdown("**Display Options**")
    show_dims   = st.checkbox("📏 Show Dimensions",True)
    show_vastu_grid = st.checkbox("🟨 Vastu Zone Grid",False)

    st.divider()

    # API Keys
    with st.expander("🔑 AI API Keys (Optional)"):
        st.caption("Keys are not stored — only used for this session")
        groq_key     = st.text_input("Groq API Key",     type="password", placeholder="gsk_...")
        gemini_key   = st.text_input("Gemini API Key",   type="password", placeholder="AIza...")
        deepseek_key = st.text_input("DeepSeek API Key", type="password", placeholder="sk-...")

    st.divider()

    # Plan password
    with st.expander("🔐 Exported Plan Password"):
        st.caption("Password for HTML/shared plan")
        plan_pw = st.text_input("Plan Password", type="password", placeholder="Leave empty = no lock")

    generate_btn = st.button("🚀 Generate Floor Plan", type="primary", use_container_width=True)


# ─────────────────────────────────────────────────────────────────
# Generate
# ─────────────────────────────────────────────────────────────────
if generate_btn:
    with st.spinner("⚙️ Building layout..."):
        try:
            rooms = create_layout(length, breadth, bhk, facing, modern, balcony, pooja)
            vastu = audit_vastu(rooms, length, breadth)

            fig = render_floor_plan(
                length, breadth, rooms, facing, bhk,
                vastu_pct=vastu["pct"],
                show_dimensions=show_dims,
                show_vastu_grid=show_vastu_grid,
            )
            html_str = generate_html(
                length, breadth, rooms, facing, bhk,
                vastu_pct=vastu["pct"],
                password=plan_pw or ""
            )

            st.session_state.rooms    = rooms
            st.session_state.fig      = fig
            st.session_state.vastu    = vastu
            st.session_state.html_str = html_str
            st.session_state.ai_results = None
            plt.close("all")
            st.success(f"✅ {len(rooms)} rooms placed — Vastu {vastu['pct']}%")
        except Exception as e:
            st.error(f"❌ Error: {e}")
            st.exception(e)


# ─────────────────────────────────────────────────────────────────
# Main Output
# ─────────────────────────────────────────────────────────────────
if st.session_state.rooms:
    rooms = st.session_state.rooms
    fig   = st.session_state.fig
    vastu = st.session_state.vastu

    # ── Top Metrics ───────────────────────────────────────────────
    total_room_area = sum(r["w"]*r["h"] for r in rooms)
    coverage_pct    = int(total_room_area / (length*breadth) * 100)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Rooms",    len(rooms))
    c2.metric("Plot Area",      f"{length*breadth:.0f} sq ft")
    c3.metric("Coverage",       f"{coverage_pct}%")
    c4.metric("Vastu Score",    f"{vastu['pct']}%",
              delta="Good" if vastu['pct']>=65 else "Needs Work")

    st.divider()

    # ── Main Tabs ─────────────────────────────────────────────────
    tab1, tab2, tab3, tab4 = st.tabs([
        "📐 Floor Plan",
        "🧿 Vastu Report",
        "🤖 AI Suggestions",
        "📊 Room Details",
    ])

    # ── Tab 1: Floor Plan + Exports ───────────────────────────────
    with tab1:
        col_plan, col_side = st.columns([2.5, 1])

        with col_plan:
            st.pyplot(fig, use_container_width=True)

        with col_side:
            st.markdown('<div class="section-head">📤 Export</div>', unsafe_allow_html=True)

            # PDF
            pdf_bytes = to_pdf(fig, dpi=200)
            st.download_button("📄 Download PDF", data=pdf_bytes,
                file_name=f"{bhk.replace(' ','_')}_{facing}_{int(length)}x{int(breadth)}.pdf",
                mime="application/pdf", use_container_width=True)

            # PNG
            png_bytes = to_png(fig, dpi=150)
            st.download_button("🖼️ Download PNG", data=png_bytes,
                file_name=f"{bhk.replace(' ','_')}_{facing}.png",
                mime="image/png", use_container_width=True)

            # SVG
            svg_bytes = to_svg(fig)
            st.download_button("🎨 Download SVG", data=svg_bytes,
                file_name=f"{bhk.replace(' ','_')}_{facing}.svg",
                mime="image/svg+xml", use_container_width=True)

            # HTML (interactive)
            html_bytes = st.session_state.html_str.encode("utf-8")
            st.download_button("🌐 Download HTML", data=html_bytes,
                file_name=f"{bhk.replace(' ','_')}_{facing}_interactive.html",
                mime="text/html", use_container_width=True,
                help="Interactive floor plan — open in browser, zoom/pan, password protected")

            # JSON
            st.download_button("📊 Download JSON", 
                data=json.dumps(rooms, indent=2).encode("utf-8"),
                file_name="layout.json", mime="application/json",
                use_container_width=True)

            st.divider()

            # Room list
            st.markdown('<div class="section-head">🏘️ Rooms</div>', unsafe_allow_html=True)
            icons = {"living":"🛋️","bedroom":"🛏️","kitchen":"🍳","bathroom":"🚿",
                     "balcony":"🌿","pooja":"🪔","dining":"🍽️","passage":"🚶","utility":"🧹"}
            for r in rooms:
                icon = icons.get(r.get("type",""),"🔲")
                area = r["w"]*r["h"]
                st.markdown(
                    f'{icon} **{r["label"]}** &nbsp; '
                    f'<small style="color:#888">{r["w"]:.0f}×{r["h"]:.0f} ft • {area:.0f} sqft</small>',
                    unsafe_allow_html=True)

    # ── Tab 2: Vastu Report ───────────────────────────────────────
    with tab2:
        v_color = "#1E8449" if vastu["pct"]>=70 else "#D35400" if vastu["pct"]>=45 else "#C0392B"
        st.progress(vastu["overall"], text=f"**Overall Vastu Score: {vastu['pct']}%**")

        st.markdown("---")
        for room_label, info in vastu["rooms"].items():
            icon   = info["icon"]
            status = info["status"].title()
            zone   = info["zone"]
            color  = {"ideal":"#1E8449","acceptable":"#D35400",
                      "avoid":"#C0392B","neutral":"#888"}.get(info["status"],"#888")
            st.markdown(
                f"{icon} **{room_label}** — Zone `{zone}` &nbsp;"
                f'<span style="color:{color};font-size:.83rem">{status}</span>',
                unsafe_allow_html=True)

        st.divider()
        with st.expander("📖 Vastu Quick Reference"):
            st.markdown("""
| Direction | Zone | Ideal For |
|-----------|------|-----------|
| SW | South-West | Master Bedroom, Heavy storage |
| SE | South-East | Kitchen (Agni) |
| NE | North-East | Pooja, Meditation (Ishaan) |
| NW | North-West | Guest room, Bathroom |
| N  | North       | Living room, Main entrance |
| E  | East        | Living, Dining, Study |
| S  | South       | Bedroom 2, Staircase |
| W  | West        | Bedroom, Study |
| C  | Centre      | Keep open — Brahmasthana |
""")

    # ── Tab 3: AI Suggestions ─────────────────────────────────────
    with tab3:
        st.markdown("#### 🤖 Multi-AI Architect Consultation")
        st.caption("Groq + Gemini + DeepSeek — all three analyze your layout simultaneously")

        user_q = st.text_input("🗣️ Ask something specific (optional)",
                                placeholder="e.g. इस plot के लिए kitchen को better कहाँ रखें?")

        ai_btn = st.button("⚡ Get AI Analysis (All 3)", type="primary")

        if ai_btn:
            has_key = any([groq_key.strip(), gemini_key.strip(), deepseek_key.strip()])
            if not has_key:
                st.warning("⚠️ Please add at least one API key in the sidebar → 🔑 AI API Keys")
            else:
                with st.spinner("🔄 Consulting all AIs in parallel..."):
                    results = get_ai_suggestions(
                        length, breadth, bhk, facing, rooms, vastu["pct"],
                        groq_key, gemini_key, deepseek_key, user_q
                    )
                    st.session_state.ai_results = results

        if st.session_state.ai_results:
            for res in st.session_state.ai_results:
                ai_color = res.get("color","#888")
                status   = res.get("status","")
                icon     = res.get("icon","🤖")
                ai_name  = res.get("ai","AI")
                t_ms     = res.get("time_ms",0)

                st.markdown(f"""
<div class="ai-card" style="--ai-color:{ai_color}">
    <div class="ai-header">
        <span style="font-size:1.2rem">{icon}</span>
        <span class="ai-name" style="color:{ai_color}">{ai_name}</span>
        <span class="ai-time">⏱ {t_ms}ms</span>
    </div>
    <div class="ai-body">{res.get("response","No response")}</div>
</div>
""", unsafe_allow_html=True)

    # ── Tab 4: Room Details Table ─────────────────────────────────
    with tab4:
        st.markdown("#### 📊 Complete Room Breakdown")

        import pandas as pd
        rows = []
        for r in rooms:
            rows.append({
                "Room":        r["label"],
                "Type":        r.get("type","").title(),
                "X (ft)":      f'{r["x"]:.1f}',
                "Y (ft)":      f'{r["y"]:.1f}',
                "Width (ft)":  f'{r["w"]:.1f}',
                "Depth (ft)":  f'{r["h"]:.1f}',
                "Area (sqft)": f'{r["w"]*r["h"]:.0f}',
                "Doors":       len(r.get("doors",[])),
                "Windows":     len(r.get("windows",[])),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Parallel plans section
        st.divider()
        st.markdown("#### ⚡ Generate Multiple Plans at Once")
        st.caption("4-5 different configurations ek saath generate karo")

        if st.button("🔄 Generate All 4 BHK Variants", use_container_width=False):
            configs = [
                {"length":length,"breadth":breadth,"bhk":bhk,"facing":"North","modern":True,"balcony":True,"pooja":True},
                {"length":length,"breadth":breadth,"bhk":bhk,"facing":"East", "modern":True,"balcony":True,"pooja":True},
                {"length":length,"breadth":breadth,"bhk":bhk,"facing":"South","modern":True,"balcony":True,"pooja":True},
                {"length":length,"breadth":breadth,"bhk":bhk,"facing":"West", "modern":True,"balcony":True,"pooja":True},
            ]
            with st.spinner("⚡ Generating 4 plans in parallel..."):
                all_plans = generate_parallel_plans(configs)

            for plan in sorted(all_plans, key=lambda p: p["config"]["facing"]):
                cfg = plan["config"]
                vsc = plan["vastu"]["pct"]
                vcol = "#1E8449" if vsc>=70 else "#D35400" if vsc>=45 else "#C0392B"
                st.markdown(
                    f'**{cfg["facing"]} Facing** — '
                    f'<span style="color:{vcol}">Vastu {vsc}%</span> — '
                    f'{len(plan["rooms"])} rooms',
                    unsafe_allow_html=True)

else:
    # ── Welcome Screen ────────────────────────────────────────────
    st.markdown("""
<div style="text-align:center;padding:4rem 2rem;color:#888">
    <div style="font-size:5rem;margin-bottom:1rem">🏠</div>
    <h2 style="color:#555;font-weight:600">Smart Floor Plan Generator</h2>
    <p style="font-size:1rem;margin:1rem 0;color:#999">
        Fill in plot details in the sidebar and click <strong>Generate</strong>
    </p>
    <div style="display:flex;justify-content:center;gap:2rem;flex-wrap:wrap;margin-top:2rem">
        <div style="background:white;padding:1.2rem 1.8rem;border-radius:12px;border:1px solid #eee;min-width:160px">
            <div style="font-size:1.8rem">⚡</div>
            <div style="font-weight:600;margin-top:.5rem">Zero Overlap</div>
            <div style="font-size:.8rem;color:#999">Rooms never collide</div>
        </div>
        <div style="background:white;padding:1.2rem 1.8rem;border-radius:12px;border:1px solid #eee;min-width:160px">
            <div style="font-size:1.8rem">🧿</div>
            <div style="font-weight:600;margin-top:.5rem">Vastu Checked</div>
            <div style="font-size:.8rem;color:#999">All 9 zones analyzed</div>
        </div>
        <div style="background:white;padding:1.2rem 1.8rem;border-radius:12px;border:1px solid #eee;min-width:160px">
            <div style="font-size:1.8rem">🤖</div>
            <div style="font-weight:600;margin-top:.5rem">3 AIs</div>
            <div style="font-size:.8rem;color:#999">Groq + Gemini + DeepSeek</div>
        </div>
        <div style="background:white;padding:1.2rem 1.8rem;border-radius:12px;border:1px solid #eee;min-width:160px">
            <div style="font-size:1.8rem">🌐</div>
            <div style="font-weight:600;margin-top:.5rem">HTML Export</div>
            <div style="font-size:.8rem;color:#999">Interactive + Password</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
