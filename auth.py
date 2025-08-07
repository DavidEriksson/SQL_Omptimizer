# auth.py
import streamlit as st
from database import get_user, add_user, verify_password

OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]

def handle_auth(supabase):
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user_email" not in st.session_state:
        st.session_state.user_email = None
    if "is_admin" not in st.session_state:
        st.session_state.is_admin = False

    if st.session_state.logged_in:
        return True

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Welcome to SQL Optimizer")
        auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])

        with auth_tab1:
            with st.form("login_form"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                login_button = st.form_submit_button("Login")

            if login_button:
                user = get_user(supabase, email)
                if not user:
                    st.error("User not found.")
                else:
                    if verify_password(user["password"], password):
                        st.session_state.logged_in = True
                        st.session_state.user_email = email
                        st.session_state.is_admin = bool(user.get("admin")) or (email in ADMIN_EMAILS)
                        return True
                    else:
                        st.error("Invalid password")

        with auth_tab2:
            with st.form("register_form"):
                new_email = st.text_input("New Email")
                new_name = st.text_input("Full Name")
                new_password = st.text_input("Password", type="password")
                register_button = st.form_submit_button("Register")

            if register_button:
                if get_user(supabase, new_email):
                    st.error("Email already exists")
                else:
                    is_admin = new_email in ADMIN_EMAILS
                    add_user(supabase, new_email, new_name, new_password, is_admin)
                    st.success("Account created. Please log in.")

    return False
