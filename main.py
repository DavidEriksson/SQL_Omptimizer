import streamlit as st
import streamlit_authenticator as stauth
import yaml
import os
from datetime import datetime, timedelta
import openai
import tiktoken

# === Secrets ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
COOKIE_KEY = st.secrets["COOKIE_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]  # List of emails

# === Create users.yaml if missing ===
if not os.path.exists("users.yaml"):
    default_user = {
        "credentials": {
            "usernames": {
                "test@example.com": {
                    "email": "test@example.com",
                    "name": "Test Admin",
                    "password": "$2b$12$kW8iElbYVXNLxjv6mQWnZORqB9V2FClzJvnUDT0bbPHb8Qbs47yqO"  # test1234
                }
            }
        },
        "cookie": {
            "expiry_days": 30,
            "name": "sql_optimizer_login"
        },
        "preauthorized": {
            "emails": ["test@example.com"]
        }
    }
    with open("users.yaml", "w") as f:
        yaml.dump(default_user, f)

# === Load config ===
with open("users.yaml", "r") as file:
    config = yaml.safe_load(file)

# === Authenticator ===
authenticator = stauth.Authenticate(
    config,
    cookie_name="sql_optimizer_login",
    key=COOKIE_KEY,
    cookie_expiry_days=30
)

# === Sidebar Login/Register ===
st.sidebar.title("Account")
auth_option = st.sidebar.radio("Choose:", ("Login", "Register"))

if auth_option == "Register":
    try:
        email, username, password = authenticator.register_user(preauthorization=False)
        if email:
            st.success("✅ User registered. Please log in.")
            # Add to config and save to file
            config["credentials"]["usernames"][email] = {
                "email": email,
                "name": username,
                "password": password
            }
            with open("users.yaml", "w") as f:
                yaml.dump(config, f)
            st.stop()
    except Exception as e:
        st.error(f"Registration error: {str(e)}")
        st.stop()

name, auth_status, username = authenticator.login("Login", "main")

if not auth_status:
    st.stop()

email = username
is_admin = email in ADMIN_EMAILS

authenticator.logout("Logout", "sidebar")

# === UI Setup ===
st.set_page_config(page_title="SQL Optimizer AI", layout="centered")
st.title("SQL Optimizer")
st.success(f"👋 Welcome {name} ({email})")
if is_admin:
    st.sidebar.success("👑 Admin Account (Unlimited)")
else:
    st.sidebar.info("👤 Standard Account")

# === Session state ===
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

if datetime.now() >= st.session_state.query_reset_time:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

if not is_admin:
    st.sidebar.markdown("### 🔒 Usage Limit")
    st.sidebar.markdown(f"Queries used: **{st.session_state.query_count}/5**")
    reset_in = st.session_state.query_reset_time - datetime.now()
    st.sidebar.caption(f"Resets in: {reset_in.seconds // 3600}h {(reset_in.seconds % 3600) // 60}m")

# === User Input ===
st.markdown("---")
st.subheader("Paste your SQL query")
sql_query = st.text_area("SQL Code", height=200, placeholder="Paste SQL here...")
task = st.selectbox("What do you want to do?", ["Explain", "Detect Issues", "Optimize", "Test"])
model = "gpt-4o-mini"
temperature = 0.3
max_tokens = 1500
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def estimate_tokens(text):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False

if st.button("Run"):
    if not sql_query.strip():
        st.error("❌ Please enter a SQL query.")
    elif not is_admin and st.session_state.query_count >= 5:
        st.error("❌ Query limit reached. Please wait for reset.")
    else:
        if not is_admin:
            st.session_state.query_count += 1
        st.session_state.run_analysis = True
        st.rerun()

if st.session_state.run_analysis:
    prompt_templates = {
        "Explain": f"""
You are an expert SQL instructor.

Explain this SQL query step-by-step, including:
- The purpose of the query
- What each clause does
- The role of each table and join
- Any assumptions about the data

Don't talk like an AI bot.

SQL Query:
{sql_query}
""",
        "Detect Issues": f"""
You are a senior SQL code reviewer.

Analyze the following SQL query and list:
- Performance problems
- Poor practices
- Logical issues
- Suggestions for improvement

Don't talk like an AI bot.

SQL Query:
{sql_query}
""",
        "Optimize": f"""
You are a SQL performance expert.

Review the query below and:
1. Suggest how to optimize it
2. Provide a revised version
3. Explain why your changes help

Don't talk like an AI bot.

SQL Query:
{sql_query}
""",
        "Test": f"""
You are a SQL testing expert.

Generate:
- 3 to 5 rows of sample data for each table used
- Expected result set based on the query
- Brief notes on how the data satisfies the query logic

Don't talk like an AI bot.

SQL Query:
{sql_query}
"""
    }

    prompt = prompt_templates[task]

    with st.spinner("🔍 Analyzing your SQL..."):
        try:
            token_estimate = estimate_tokens(prompt)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            reply = response.choices[0].message.content
            st.success("✅ Analysis complete!")
            st.markdown("### Result")
            st.markdown(reply)
            st.caption(f"🔢 Estimated tokens: {token_estimate} • Model: {model}")
            st.download_button("📋 Copy Result", reply, file_name="sql_analysis.txt")
        except Exception as e:
            st.error(f"Error: {str(e)}")

    st.session_state.run_analysis = False
