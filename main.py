import streamlit as st
from datetime import datetime, timedelta

# Import custom modules
from config import init_page_config, apply_custom_css
from database import *
from auth import login_page
from components.sidebar import render_sidebar
from pages.home import home_page
from pages.optimizer import optimizer_page
from pages.history import history_page
from pages.analytics import analytics_page
from pages.users import users_page
from pages.natural_language import natural_language_page

# === Page Configuration ===
init_page_config()
apply_custom_css()

# Hide the default Streamlit file navigation sidebar
st.markdown("""
<style>
    /* Hide the Streamlit default sidebar navigation */
    [data-testid="stSidebarNav"] {
        display: none;
    }
    
    /* Hide the expander arrow in sidebar */
    [data-testid="stSidebarNav"] > ul {
        display: none;
    }
    
    /* Remove extra padding when nav is hidden */
    [data-testid="stSidebarUserContent"] {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

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
    # Don't show sidebar when not logged in
    st.markdown("""
    <style>
        [data-testid="stSidebar"] {
            display: none;
        }
    </style>
    """, unsafe_allow_html=True)
    login_page()
else:
    # Render sidebar only when logged in
    render_sidebar()
    
    # Route to appropriate page
    if st.session_state.current_page == "Home":
        home_page()
    elif st.session_state.current_page == "Optimizer":
        optimizer_page()
    elif st.session_state.current_page == "Natural Language":
        natural_language_page()
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