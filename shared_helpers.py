# shared_helpers.py

def sanitize_key(key: str) -> str:
    return key.replace(" ", "_").replace("|", "_").replace("&", "and").lower()

def render_match(p1, p2, default="Tie", readonly=False, key_prefix="", stage=""):
    import streamlit as st

    key = f"{stage}_{key_prefix}_winner"
    options = [p1["name"], p2["name"], "Tie"]

    if readonly:
        st.write(f"**{p1['name']} vs {p2['name']}** — Winner: **{default}**")
        return default

    return st.radio(f"{p1['name']} vs {p2['name']}", options, index=options.index(default), key=key)
