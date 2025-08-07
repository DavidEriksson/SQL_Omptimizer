import streamlit as st
from database import get_user, add_user, verify_password
from config import ADMIN_EMAILS

def login_page():
    """Render the login/register page"""
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Welcome to SQL Optimizer")
        
        auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])
        
        with auth_tab1:
            login_form()
        
        with auth_tab2:
            register_form()
        
        # Info cards
        st.markdown("---")
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.markdown("""
            <div class="metric-container">
                <h4>Analyze</h4>
                <p>Get detailed explanations of your SQL queries</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_info2:
            st.markdown("""
            <div class="metric-container">
                <h4>Optimize</h4>
                <p>Improve query performance with AI suggestions</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_info3:
            st.markdown("""
            <div class="metric-container">
                <h4>Test</h4>
                <p>Generate test data and validate your queries</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.stop()

def login_form():
    """Render the login form"""
    with st.form("login_form"):
        email = st.text_input("Email", placeholder="Enter your email")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        login_button = st.form_submit_button("Login", use_container_width=True)

    if login_button:
        user = get_user(email)
        if not user:
            st.error("User not found. Please check your email or register.")
        else:
            stored_password = user['password']
            
            if verify_password(stored_password, password):
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.is_admin = user.get('is_admin', False) or (email in ADMIN_EMAILS)
                st.rerun()
            else:
                st.error("Invalid password")

def register_form():
    """Render the registration form"""
    with st.form("register_form"):
        new_email = st.text_input("Email", placeholder="Enter your email")
        new_name = st.text_input("Full Name", placeholder="Enter your full name")
        new_password = st.text_input("Password", type="password", placeholder="Create a password")
        register_button = st.form_submit_button("Create Account", use_container_width=True)

    if register_button:
        if get_user(new_email):
            st.error("Email already exists")
        else:
            is_admin = new_email in ADMIN_EMAILS
            if add_user(new_email, new_name, new_password, is_admin):
                st.success("Account created successfully! Please log in.")