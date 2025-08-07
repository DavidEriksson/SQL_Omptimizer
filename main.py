# main.py
from auth import handle_auth
from ui_pages import render_ui
from database import init_db

import streamlit as st

# === Init database ===
conn, cursor = init_db()

# === Authentication ===
auth_success = handle_auth(cursor)
if not auth_success:
    st.stop()

# === Render UI ===
render_ui(conn, cursor)
