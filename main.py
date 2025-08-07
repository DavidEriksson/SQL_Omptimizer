import streamlit as st
from datetime import datetime, timedelta

# Import custom modules
from config import init_page_config, apply_custom_css
from database import *
from auth import login_page
from components.sidebar import render_sidebar
from views.home import home_page
from views.optimizer import optimizer_page
from views.history import history_page
from views.analytics import analytics_page
from views.users import users_page

# === Page Configuration ===
init_page_config()
apply_custom_css()

# === Session State Initialization ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
if "formatted_sql" not in st.session_state:
    st.session_state.formatted_sql = None
if "selected_history_query" not in st.session_state:
    st.session_state.selected_history_query = None
if "current_sql_query" not in st.session_state:
    st.session_state.current_sql_query = ""
if "last_analytics_update" not in st.session_state:
    st.session_state.last_analytics_update = None
if "cached_analytics" not in st.session_state:
    st.session_state.cached_analytics = None

# === Header ===
st.markdown("""
<div class="main-header">
    <h1>SQL Optimizer AI</h1>
    <p>Analyze, optimize, and understand your SQL queries with AI-powered insights</p>
</div>
""", unsafe_allow_html=True)

# === Main Application Flow ===
if not st.session_state.logged_in:
    login_page()
else:
    # Render sidebar
    render_sidebar()
    
    # Route to appropriate page
    if st.session_state.current_page == "Home":
        home_page()
    elif st.session_state.current_page == "Optimizer":
        optimizer_page()
    elif st.session_state.current_page == "History":
        history_page()
    elif st.session_state.current_page == "Analytics" and st.session_state.is_admin:
        analytics_page()
    elif st.session_state.current_page == "Users" and st.session_state.is_admin:
        users_page()
    
    # Footer
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; color: #666; padding: 2rem 0;">
        <p>SQL Optimizer AI - Powered by GPT-4o Mini</p>
        <p>Built with Streamlit | Database by Supabase</p>
    </div>
    """, unsafe_allow_html=True)