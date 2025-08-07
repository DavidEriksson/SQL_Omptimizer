import streamlit as st
from datetime import datetime, timedelta
from database import get_user

def render_sidebar():
    """Render the sidebar navigation and user info"""
    with st.sidebar:
        # Get user's name
        user = get_user(st.session_state.user_email)
        user_name = user['name'] if user else st.session_state.user_email
        
        # User status card
        st.markdown(f"""
        <div class="status-card">
            <h3>Welcome</h3>
            <p><strong>{user_name}</strong></p>
            <p>{"Admin Account" if st.session_state.is_admin else "Standard User"}</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Navigation
        st.markdown("### Navigation")
        
        if st.button("Home", key="nav_home", use_container_width=True, 
                     type="primary" if st.session_state.current_page == "Home" else "secondary"):
            st.session_state.current_page = "Home"
            st.rerun()
        
        if st.button("SQL Optimizer", key="nav_optimizer", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Optimizer" else "secondary"):
            st.session_state.current_page = "Optimizer"
            st.rerun()
        
        if st.button("Natural Language", key="nav_natural", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Natural Language" else "secondary"):
            st.session_state.current_page = "Natural Language"
            st.rerun()
        
        if st.button("Query History", key="nav_history", use_container_width=True,
                     type="primary" if st.session_state.current_page == "History" else "secondary"):
            st.session_state.current_page = "History"
            st.rerun()
        
        if st.session_state.is_admin:
            if st.button("Analytics", key="nav_analytics", use_container_width=True,
                         type="primary" if st.session_state.current_page == "Analytics" else "secondary"):
                st.session_state.current_page = "Analytics"
                st.rerun()
            
            if st.button("User Management", key="nav_users", use_container_width=True,
                         type="primary" if st.session_state.current_page == "Users" else "secondary"):
                st.session_state.current_page = "Users"
                st.rerun()
        
        st.markdown("---")
        
        # Usage tracker
        if not st.session_state.is_admin:
            if datetime.now() >= st.session_state.query_reset_time:
                st.session_state.query_count = 0
                st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)
            
            st.markdown("### Usage")
            progress = st.session_state.query_count / 5
            st.progress(progress)
            st.markdown(f"**{st.session_state.query_count}/5** queries used today")
            
            reset_in = st.session_state.query_reset_time - datetime.now()
            hours = reset_in.seconds // 3600
            minutes = (reset_in.seconds % 3600) // 60
            st.caption(f"Resets in: {hours}h {minutes}m")
            
            if st.session_state.query_count >= 5:
                st.error("Daily limit reached")
        else:
            st.markdown("### Usage")
            st.success("Unlimited queries")
        
        st.markdown("---")
        
        # Settings
        st.markdown("### Settings")
        if st.button("Logout", use_container_width=True, type="secondary"):
            st.session_state.logged_in = False
            st.session_state.user_email = None
            st.session_state.is_admin = False
            st.session_state.current_page = "Home"
            st.rerun()