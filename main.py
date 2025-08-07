
import streamlit as st
import streamlit.components.v1
import openai
import tiktoken
from datetime import datetime, timedelta
from supabase import create_client, Client
import bcrypt
import pandas as pd

# === Load from Streamlit Secrets (for Streamlit Cloud) ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# === Initialize Supabase client ===
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# === Supabase Wrapper Functions ===
def add_user(email, name, password, is_admin=False):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    data = {
        "email": email,
        "name": name,
        "password": hashed_password,
        "admin": is_admin
    }
    result = supabase.table("users").insert(data).execute()
    return result

def get_user(email):
    result = supabase.table("users").select("*").eq("email", email).execute()
    rows = result.data
    return rows[0] if rows else None

def verify_password(stored_password, provided_password):
    return bcrypt.checkpw(provided_password.encode(), stored_password.encode())

def log_query(user_email, task_type, query_length, tokens_used=None, success=True, error_message=None):
    data = {
        "user_email": user_email,
        "task_type": task_type,
        "query_length": query_length,
        "tokens_used": tokens_used,
        "success": success,
        "error_message": error_message,
        "timestamp": datetime.utcnow().isoformat()
    }
    supabase.table("query_logs").insert(data).execute()

def save_query_to_history(user_email, query_text, task_type, result_text=None, query_name=None):
    data = {
        "user_email": user_email,
        "query_text": query_text,
        "task_type": task_type,
        "result_text": result_text,
        "query_name": query_name,
        "timestamp": datetime.utcnow().isoformat()
    }
    response = supabase.table("query_history").insert(data).execute()
    if response.data:
        return response.data[0]["id"]
    return None

def get_user_query_history(user_email, limit=50):
    result = supabase.table("query_history").select("*").eq("user_email", user_email).order("timestamp", desc=True).limit(limit).execute()
    return result.data if result.data else []

def get_user_favorites(user_email):
    result = supabase.table("query_history").select("*").eq("user_email", user_email).eq("is_favorite", True).order("timestamp", desc=True).execute()
    return result.data if result.data else []

def toggle_favorite(query_id):
    current = supabase.table("query_history").select("is_favorite").eq("id", query_id).execute()
    rows = current.data
    if not rows:
        return False
    new_status = not rows[0]["is_favorite"]
    supabase.table("query_history").update({"is_favorite": new_status}).eq("id", query_id).execute()
    return new_status

def delete_query_from_history(query_id, user_email):
    response = supabase.table("query_history").delete().eq("id", query_id).eq("user_email", user_email).execute()
    return response.status_code == 200

def update_query_name(query_id, user_email, new_name):
    response = supabase.table("query_history").update({"query_name": new_name}).eq("id", query_id).eq("user_email", user_email).execute()
    return response.status_code == 200

def get_analytics_data():
    analytics = {}

    analytics['total_queries'] = supabase.rpc("count_queries").execute().data
    analytics['success_rate'] = supabase.rpc("success_rate").execute().data
    analytics['queries_by_task'] = supabase.rpc("queries_by_task").execute().data
    analytics['total_users'] = supabase.rpc("count_users").execute().data
    analytics['active_users_7d'] = supabase.rpc("active_users_7d").execute().data
    analytics['avg_query_length'] = supabase.rpc("avg_query_length").execute().data
    analytics['total_tokens'] = supabase.rpc("sum_tokens_used").execute().data

    return analytics


# === Session State ===
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

# === AUTH GUARD ===
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### Welcome to SQL Optimizer")
        auth_tab1, auth_tab2 = st.tabs(["Login", "Register"])

        with auth_tab1:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="Enter your email")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                login_button = st.form_submit_button("Login", use_container_width=True)

            if login_button:
                user = get_user(email)
                if not user:
                    st.error("User not found. Please check your email or register.")
                else:
                    stored_password = user["password"]
                    if verify_password(stored_password, password):
                        st.session_state.logged_in = True
                        st.session_state.user_email = email
                        st.session_state.is_admin = user.get("admin", False) or (email in ADMIN_EMAILS)
                        st.rerun()
                    else:
                        st.error("Invalid password")

        with auth_tab2:
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
                    add_user(new_email, new_name, new_password, is_admin)
                    st.success("Account created successfully! Please log in.")

    st.stop()

# === UI fortsätter här ===
# [REMAINING UI LOGIC INSERTION POINT - will be done next]


# === Sidebar ===
with st.sidebar:
    st.markdown(f"""
    <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1.5rem; border-radius: 15px; text-align: center; margin: 1rem 0;'>
        <h3>Welcome</h3>
        <p><strong>{st.session_state.user_email}</strong></p>
        <p>{"Admin Account" if st.session_state.is_admin else "Standard User"}</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Navigation")
    if st.button("Home", use_container_width=True):
        st.session_state.current_page = "Home"
        st.rerun()
    if st.button("SQL Optimizer", use_container_width=True):
        st.session_state.current_page = "Optimizer"
        st.rerun()
    if st.button("Query History", use_container_width=True):
        st.session_state.current_page = "History"
        st.rerun()
    if st.session_state.is_admin:
        if st.button("Analytics", use_container_width=True):
            st.session_state.current_page = "Analytics"
            st.rerun()

    st.markdown("---")
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
        st.success("Unlimited queries")

    st.markdown("---")
    st.markdown("### Settings")
    if st.button("Logout", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.session_state.is_admin = False
        st.session_state.current_page = "Home"
        st.rerun()

# === SQL Optimizer Page ===
if st.session_state.current_page == "Optimizer":
    st.markdown("## SQL Query Optimizer")

    col1, col2 = st.columns([3, 1])
    with col1:
        default_value = st.session_state.current_sql_query or ""
        sql_query = st.text_area("SQL Query", value=default_value, height=300, key="sql_input")

    with col2:
        task = st.selectbox("Analysis Type", ["Explain", "Optimize", "Detect Issues", "Test"])
        task_descriptions = {
            "Explain": "Get a detailed step-by-step explanation",
            "Optimize": "Improve performance and efficiency",
            "Detect Issues": "Find problems and bad practices",
            "Test": "Generate test data and expected results"
        }
        st.info(task_descriptions[task])
        if st.button("Format SQL"):
            formatted = format_sql(sql_query)
            st.session_state.current_sql_query = formatted
            st.rerun()
        analyze = st.button("Analyze Query", disabled=(not st.session_state.is_admin and st.session_state.query_count >= 5))

    if analyze:
        if not sql_query.strip():
            st.error("Please enter a SQL query.")
        elif not st.session_state.is_admin and st.session_state.query_count >= 5:
            st.error("Daily query limit reached.")
        else:
            if not st.session_state.is_admin:
                st.session_state.query_count += 1

            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            model = "gpt-4o-mini"
            temperature = 0.3
            max_tokens = 1500

            def estimate_tokens(text):
                enc = tiktoken.encoding_for_model(model)
                return len(enc.encode(text))

            prompt_templates = {
                "Explain": f"""Provide a comprehensive analysis of this SQL query:
{sql_query}""",
                "Optimize": f"""Optimize the following SQL query:
{sql_query}""",
                "Detect Issues": f"""Identify issues in this SQL query:
{sql_query}""",
                "Test": f"""Generate test data and results for this SQL query:
{sql_query}"""
            }

            prompt = prompt_templates[task]
            tokens = estimate_tokens(prompt)

            with st.spinner("Analyzing..."):
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    reply = response.choices[0].message.content
                    log_query(st.session_state.user_email, task, len(sql_query), tokens_used=tokens)
                    history_id = save_query_to_history(st.session_state.user_email, sql_query, task, reply)

                    st.success("Analysis complete")
                    st.markdown(reply)
                    if history_id:
                        st.caption(f"Saved to history (ID {history_id})")

                except Exception as e:
                    log_query(st.session_state.user_email, task, len(sql_query), success=False, error_message=str(e))
                    st.error(f"Error: {str(e)}")


# === History Page ===
elif st.session_state.current_page == "History":
    st.markdown("## Query History")
    history = get_user_query_history(st.session_state.user_email)
    favorites = get_user_favorites(st.session_state.user_email)
    tab1, tab2 = st.tabs(["Recent Queries", "Favorites"])

    with tab1:
        st.markdown("### Recent Queries")
        if history:
            for item in history:
                st.markdown("---")
                st.markdown(f"**Task:** {item['task_type']} | **Date:** {item['timestamp']}")
                if item.get("query_name"):
                    st.markdown(f"**Name:** {item['query_name']}")
                st.code(item['query_text'], language="sql")
                if item.get("result_text"):
                    with st.expander("View Result"):
                        st.markdown(item["result_text"])
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("Use", key=f"use_{item['id']}"):
                        st.session_state.selected_history_query = item["query_text"]
                        st.session_state.current_page = "Optimizer"
                        st.rerun()
                with col2:
                    label = "Unfavorite" if item.get("is_favorite") else "Favorite"
                    if st.button(label, key=f"fav_{item['id']}"):
                        toggle_favorite(item["id"])
                        st.rerun()
                with col3:
                    if st.button("Delete", key=f"del_{item['id']}"):
                        if delete_query_from_history(item["id"], st.session_state.user_email):
                            st.success("Query deleted")
                            st.rerun()
        else:
            st.info("No query history found")

    with tab2:
        st.markdown("### Favorite Queries")
        if favorites:
            for item in favorites:
                st.markdown("---")
                st.markdown(f"**Task:** {item['task_type']} | **Date:** {item['timestamp']}")
                if item.get("query_name"):
                    st.markdown(f"**Name:** {item['query_name']}")
                st.code(item['query_text'], language="sql")
                if item.get("result_text"):
                    with st.expander("View Result"):
                        st.markdown(item["result_text"])
        else:
            st.info("No favorites yet")

# === Analytics Page ===
elif st.session_state.current_page == "Analytics" and st.session_state.is_admin:
    st.markdown("## Analytics Dashboard")
    analytics = get_analytics_data()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Users", analytics["total_users"])
    col2.metric("Total Queries", analytics["total_queries"])
    col3.metric("Success Rate", f"{analytics['success_rate']:.1f}%")

    st.markdown("### By Task")
    task_data = analytics["queries_by_task"]
    if task_data:
        df = pd.DataFrame(task_data)
        st.dataframe(df)
    else:
        st.info("No task data")

    st.markdown("### Other Stats")
    st.write(f"Average Query Length: {analytics['avg_query_length']}")
    st.write(f"Total Tokens Used: {analytics['total_tokens']}")
