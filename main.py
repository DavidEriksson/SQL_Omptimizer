import streamlit as st
import openai
import tiktoken
from datetime import datetime, timedelta
import sqlite3
import bcrypt

# === Load from Streamlit Secrets ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]  # list of admin emails

# === SQLite Database Setup ===
conn = sqlite3.connect('users.db', check_same_thread=False)
cursor = conn.cursor()

# Create users table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    password TEXT NOT NULL,
    is_admin BOOLEAN NOT NULL
)
''')
conn.commit()

def add_user(email, name, password, is_admin=False):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor.execute('''
    INSERT INTO users (email, name, password, is_admin) VALUES (?, ?, ?, ?)
    ''', (email, name, hashed_password, is_admin))
    conn.commit()

def get_user(email):
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    return cursor.fetchone()

def verify_password(stored_password, provided_password):
    return bcrypt.checkpw(provided_password.encode(), stored_password.encode())

# === Streamlit UI ===
st.set_page_config(page_title="SQL Optimizer AI", layout="centered")
st.title("SQL Optimizer")

# === Session state init ===
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "is_admin" not in st.session_state:
    st.session_state.is_admin = False
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

# === Login/Register UI ===
if not st.session_state.logged_in:
    auth_option = st.sidebar.radio("Account", ("Login", "Register"))

    if auth_option == "Register":
        with st.form("register_form"):
            new_email = st.text_input("Email")
            new_name = st.text_input("Name")
            new_password = st.text_input("Password", type="password")
            register_button = st.form_submit_button("Register")

        if register_button:
            if get_user(new_email):
                st.error("Email already exists")
            else:
                add_user(new_email, new_name, new_password)
                st.success("✅ User registered! Please log in.")

    else:  # Login
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login_button = st.form_submit_button("Login")

        if login_button:
            user = get_user(email)
            if user and verify_password(user[2], password):
                st.session_state.logged_in = True
                st.session_state.user_email = email
                st.session_state.is_admin = user[3]
                st.experimental_rerun()
            else:
                st.error("Invalid email or password")

    st.stop()

# === Logged in ===
# === Logged in ===
st.success(f"👋 Welcome {st.session_state.user_email}")
if st.session_state.is_admin:
    st.sidebar.success("👑 Admin Account (Unlimited)")
else:
    st.sidebar.info("👤 Standard Account")

if st.sidebar.button("Logout"):
    st.session_state.logged_in = False
    st.session_state.user_email = None
    st.session_state.is_admin = False
    st.experimental_rerun()

# Reset query count if necessary
if datetime.now() >= st.session_state.query_reset_time:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

if not st.session_state.is_admin:
    st.sidebar.markdown("### 🔒 Usage Limit")
    st.sidebar.markdown(f"Queries used: **{st.session_state.query_count}/5**")
    reset_in = st.session_state.query_reset_time - datetime.now()
    st.sidebar.caption(f"Resets in: {reset_in.seconds // 3600}h {(reset_in.seconds % 3600) // 60}m")

# === Input ===
st.markdown("---")
st.subheader("Paste your SQL query")
sql_query = st.text_area("SQL Code", height=200, placeholder="Paste SQL here...")
task = st.selectbox("What do you want to do?", ["Explain", "Detect Issues", "Optimize", "Test"])

# === GPT Setup ===
model = "gpt-4o-mini"
temperature = 0.3
max_tokens = 1500
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def estimate_tokens(text):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False

# === Run Button ===
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

# === Prompt & GPT Execution ===
if st.session_state.run_analysis:
    prompt_templates = {
        "Explain": f"""You are an expert SQL instructor.

Explain this SQL query step-by-step, including:
- The purpose of the query
- What each clause does
- The role of each table and join
- Any assumptions about the data

Don't talk like an AI bot.

SQL Query:
{sql_query}
""",
        "Detect Issues": f"""You are a senior SQL code reviewer.

Analyze the following SQL query and list:
- Performance problems
- Poor practices
- Logical issues
- Suggestions for improvement

Don't talk like an AI bot.

SQL Query:
{sql_query}
""",
        "Optimize": f"""You are a SQL performance expert.

Review the query below and:
1. Suggest how to optimize it
2. Provide a revised version
3. Explain why your changes help

Don't talk like an AI bot.

SQL Query:
{sql_query}
""",
        "Test": f"""You are a SQL testing expert.

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
