# ui_pages.py
import streamlit as st
import openai
import pandas as pd
from datetime import datetime

from utils import format_sql, estimate_tokens
from database import (
    log_query, save_query_to_history,
    get_user_query_history, get_user_favorites,
    toggle_favorite, delete_query_from_history,
    update_query_name
)
from constants import TASK_DESCRIPTIONS, PROMPT_TEMPLATES

def render_ui(supabase):
    user_email = st.session_state.user_email
    is_admin = st.session_state.is_admin

    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Go to", ["Home", "Optimizer", "History"] + (["Analytics", "Users"] if is_admin else []))
    st.session_state.current_page = page

    if page == "Home":
        st.header("Welcome back!")
        st.write(f"Logged in as: **{user_email}**")

    elif page == "Optimizer":
        st.header("SQL Query Optimizer")

        sql_query = st.text_area("SQL Query", value=st.session_state.current_sql_query, height=300)
        st.session_state.current_sql_query = sql_query

        task = st.selectbox("Task Type", list(TASK_DESCRIPTIONS.keys()))
        st.caption(TASK_DESCRIPTIONS[task])

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Format SQL"):
                st.session_state.current_sql_query = format_sql(sql_query)
                st.experimental_rerun()

        with col2:
            disabled = not is_admin and st.session_state.query_count >= 5
            if st.button("Run Analysis", disabled=disabled):
                run_query_analysis(supabase, sql_query, task)

    elif page == "History":
        st.header("Query History")
        display_query_history(supabase, user_email)

    elif page == "Analytics" and is_admin:
        st.header("Analytics Dashboard")
        st.info("Analytics will be implemented here.")

    elif page == "Users" and is_admin:
        st.header("User Management")
        st.info("User management will be implemented here.")

def run_query_analysis(supabase, sql_query, task):
    if not sql_query.strip():
        st.warning("SQL query is empty.")
        return

    prompt = PROMPT_TEMPLATES[task].format(sql_query=sql_query)
    token_estimate = estimate_tokens(prompt)

    try:
        client = openai.OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1500
        )
        reply = response.choices[0].message.content

        log_query(supabase, st.session_state.user_email, task, len(sql_query), token_estimate, success=True)
        history_id = save_query_to_history(supabase, st.session_state.user_email, sql_query, task, reply)

        st.success("Analysis complete. Saved to history.")
        st.markdown("### Result")
        st.markdown(reply)

    except Exception as e:
        log_query(supabase, st.session_state.user_email, task, len(sql_query), success=False, error_message=str(e))
        st.error(f"Failed: {e}")

def display_query_history(supabase, user_email):
    history = get_user_query_history(supabase, user_email) or []
    favorites = get_user_favorites(supabase, user_email) or []

    tab1, tab2 = st.tabs(["Recent", "Favorites"])

    with tab1:
        if not history:
            st.info("No history yet.")
            return

        for q in history:
            query_id = q.get("id")
            query_text = q.get("query_text")
            task_type = q.get("task_type")
            result_text = q.get("result_text")
            is_fav = q.get("is_favorite", False)
            name = q.get("query_name")
            timestamp = q.get("timestamp")

            with st.expander(f"{name or task_type} - {timestamp[:16]}"):
                st.code(query_text)
                if result_text:
                    st.markdown(result_text)

                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Use", key=f"use_{query_id}"):
                        st.session_state.current_sql_query = query_text
                        st.session_state.current_page = "Optimizer"
                        st.experimental_rerun()
                with col2:
                    if st.button("⭐" if not is_fav else "Unstar", key=f"fav_{query_id}"):
                        toggle_favorite(supabase, query_id)
                        st.experimental_rerun()
                with col3:
                    if st.button("Delete", key=f"del_{query_id}"):
                        delete_query_from_history(supabase, query_id, user_email)
                        st.experimental_rerun()

    with tab2:
        if not favorites:
            st.info("No favorites yet.")
            return

        for q in favorites:
            query_id = q.get("id")
            query_text = q.get("query_text")
            task_type = q.get("task_type")
            result_text = q.get("result_text")
            name = q.get("query_name")
            timestamp = q.get("timestamp")

            with st.expander(f"⭐ {name or task_type} - {timestamp[:16]}"):
                st.code(query_text)
                if result_text:
                    st.markdown(result_text)

                new_name = st.text_input("Rename", value=name or "", key=f"rename_{query_id}")
                if st.button("Update Name", key=f"update_{query_id}"):
                    update_query_name(supabase, query_id, user_email, new_name)
                    st.experimental_rerun()
