"""
ai_engine.py — Multi-AI Layout Suggestion Engine
=================================================
Groq (Llama3), Gemini (Google), DeepSeek — parallel execution.
Each AI gives layout suggestions, Vastu tips, improvement ideas.
"""
from __future__ import annotations
import os, json, asyncio, time
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed


# ─────────────────────────────────────────────────────────────────
# Prompt Builder
# ─────────────────────────────────────────────────────────────────
def build_prompt(length, breadth, bhk, facing, rooms, vastu_pct, user_query=""):
    room_summary = "\n".join(
        f"  - {r['label']}: {r['w']:.0f}×{r['h']:.0f} ft = {r['w']*r['h']:.0f} sqft"
        for r in rooms
    )
    base = f"""You are an expert Indian architect and Vastu consultant.

PLOT DETAILS:
- Size: {length}×{breadth} feet ({length*breadth:.0f} sq ft)
- BHK: {bhk}
- Facing: {facing}
- Current Vastu Score: {vastu_pct}%

CURRENT ROOM LAYOUT:
{room_summary}

YOUR TASK:
1. Analyze this floor plan critically
2. Point out 2-3 specific Vastu issues (if any)
3. Give 3 concrete improvement suggestions
4. Rate this layout out of 10 for: Space Efficiency, Vastu Compliance, Modern Living
5. One "Pro Tip" for this specific plot size

{f'USER QUESTION: {user_query}' if user_query else ''}

Reply in a mix of Hindi and English. Be specific, practical, not generic.
Keep response under 250 words. Use bullet points."""
    return base


# ─────────────────────────────────────────────────────────────────
# Individual AI Callers
# ─────────────────────────────────────────────────────────────────

def _call_groq(prompt: str, api_key: str) -> Dict:
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        t0 = time.time()
        resp = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[{"role":"user","content":prompt}],
            max_tokens=600,
            temperature=0.7,
        )
        return {
            "ai": "Groq (Llama3-70B)",
            "icon": "⚡",
            "color": "#FF6B35",
            "response": resp.choices[0].message.content,
            "time_ms": int((time.time()-t0)*1000),
            "status": "success"
        }
    except Exception as e:
        return {"ai":"Groq","icon":"⚡","color":"#FF6B35",
                "response":f"Error: {str(e)}","status":"error","time_ms":0}


def _call_gemini(prompt: str, api_key: str) -> Dict:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        t0 = time.time()
        resp = model.generate_content(prompt)
        return {
            "ai": "Gemini 1.5 Flash",
            "icon": "🔵",
            "color": "#4285F4",
            "response": resp.text,
            "time_ms": int((time.time()-t0)*1000),
            "status": "success"
        }
    except Exception as e:
        return {"ai":"Gemini","icon":"🔵","color":"#4285F4",
                "response":f"Error: {str(e)}","status":"error","time_ms":0}


def _call_deepseek(prompt: str, api_key: str) -> Dict:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
        t0 = time.time()
        resp = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role":"user","content":prompt}],
            max_tokens=600,
            temperature=0.7,
        )
        return {
            "ai": "DeepSeek V3",
            "icon": "🌊",
            "color": "#1A73E8",
            "response": resp.choices[0].message.content,
            "time_ms": int((time.time()-t0)*1000),
            "status": "success"
        }
    except Exception as e:
        return {"ai":"DeepSeek","icon":"🌊","color":"#1A73E8",
                "response":f"Error: {str(e)}","status":"error","time_ms":0}


# ─────────────────────────────────────────────────────────────────
# Parallel Multi-AI Call
# ─────────────────────────────────────────────────────────────────

def get_ai_suggestions(
    length, breadth, bhk, facing, rooms, vastu_pct,
    groq_key="", gemini_key="", deepseek_key="",
    user_query=""
) -> List[Dict]:
    """
    Teeno AIs ko parallel mein call karo.
    Returns list of results from all available AIs.
    """
    prompt = build_prompt(length, breadth, bhk, facing, rooms, vastu_pct, user_query)

    tasks = []
    if groq_key.strip():
        tasks.append(("groq",    _call_groq,     groq_key))
    if gemini_key.strip():
        tasks.append(("gemini",  _call_gemini,   gemini_key))
    if deepseek_key.strip():
        tasks.append(("deepseek",_call_deepseek, deepseek_key))

    if not tasks:
        return [{"ai":"No API Keys","icon":"⚠️","color":"#888",
                 "response":"Please add at least one API key in Settings.",
                 "status":"error","time_ms":0}]

    results = []
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        futures = {executor.submit(fn, prompt, key): name
                   for name, fn, key in tasks}
        for future in as_completed(futures):
            results.append(future.result())

    return results


# ─────────────────────────────────────────────────────────────────
# Multi-Plan Parallel Generation
# ─────────────────────────────────────────────────────────────────

def generate_parallel_plans(configs: List[Dict]) -> List[Dict]:
    """
    Multiple floor plan configurations ek saath generate karo.
    Each config: {length, breadth, bhk, facing, modern, balcony, pooja}
    Returns list of {config, rooms, vastu} dicts.
    """
    from layout_engine import create_layout, audit_vastu

    def _gen(cfg):
        rooms = create_layout(
            cfg["length"], cfg["breadth"], cfg["bhk"],
            cfg.get("facing","North"), cfg.get("modern",True),
            cfg.get("balcony",True),   cfg.get("pooja",True)
        )
        vastu = audit_vastu(rooms, cfg["length"], cfg["breadth"])
        return {"config":cfg, "rooms":rooms, "vastu":vastu}

    results = []
    with ThreadPoolExecutor(max_workers=min(len(configs),5)) as executor:
        futures = [executor.submit(_gen, cfg) for cfg in configs]
        for f in as_completed(futures):
            results.append(f.result())
    return results
