# main.py
from auth import handle_auth
from ui_pages import render_ui
from database import init_db
import streamlit as st

# === Init database ===
supabase = init_db()

# === Authentication ===
auth_success = handle_auth(supabase)
if not auth_success:
    st.stop()

# === Render UI ===
render_ui(supabase)
