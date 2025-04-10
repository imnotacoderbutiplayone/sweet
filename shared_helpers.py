# shared_helpers.py

import streamlit as st

def sanitize_key(key: str) -> str:
    return key.replace(" ", "_").replace("|", "_").replace("&", "and").replace(":", "_").lower()

def render_match(p1, p2, default="Tie", readonly=False, key_prefix="", stage=""):
    key = f"{stage}_{key_prefix}_winner"
    options = [p1["name"], p2["name"], "Tie"]
    if readonly:
        st.write(f"**{p1['name']} vs {p2['name']}** — Winner: **{default}**")
        return default
    return st.radio(f"{p1['name']} vs {p2['name']}", options, index=options.index(default), key=key)

def get_winner_player(p1, p2, winner_name):
    if winner_name == p1["name"]:
        return p1
    elif winner_name == p2["name"]:
        return p2
    else:
        return {"name": "Tie"}
