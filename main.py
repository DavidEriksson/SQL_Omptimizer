import streamlit as st
import openai
import tiktoken
import streamlit_authenticator as stauth
from datetime import datetime, timedelta

# === Secrets ===
GOOGLE_CLIENT_ID = st.secrets["GOOGLE_CLIENT_ID"]
GOOGLE_CLIENT_SECRET = st.secrets["GOOGLE_CLIENT_SECRET"]
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]
COOKIE_KEY = st.secrets["COOKIE_KEY"]

# === OAuth Configuration ===
oauth_config = {
    "provider": "google",
    "client_id": GOOGLE_CLIENT_ID,
    "client_secret": GOOGLE_CLIENT_SECRET,
    "redirect_uri": "https://sqlomptimizer.streamlit.app"
}

# === Authenticator Setup ===
credentials = {"usernames": {}}

authenticator = stauth.Authenticate(
    credentials=credentials,
    cookie_name="sqloptimizer",
    key=COOKIE_KEY,
    oauth=oauth_config
)

authenticator.login()

# === Authentication Check ===
if not st.session_state["authentication_status"]:
    st.warning("Please log in with Google to continue.")
    st.stop()

# === Identify User ===
email = st.session_state["email"]
name = st.session_state["name"]
is_admin = email in ADMIN_EMAILS

# === Page Setup ===
st.set_page_config(page_title="SQL Optimizer AI", layout="centered")
st.title("SQL Optimizer")
st.success(f"👋 Welcome {name} ({email})")
if is_admin:
    st.sidebar.success("👑 Admin Account (Unlimited)")
else:
    st.sidebar.info("👤 Standard Account")

# === Query Limit ===
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

# === GPT Model Config ===
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

# === Prompt Builder + GPT Call ===
if st.session_state.run_analysis:
    if task == "Explain":
        prompt = f"""You are an expert SQL instructor.

Explain this SQL query step-by-step, including:
- The purpose of the query
- What each clause does
- The role of each table and join
- Any assumptions about the data

SQL Query:
{sql_query}
"""
    elif task == "Detect Issues":
        prompt = f"""You are a senior SQL code reviewer.

Analyze the SQL query and list:
- Performance problems
- Poor practices
- Logical issues
- Suggestions for improvement

SQL Query:
{sql_query}
"""
    elif task == "Optimize":
        prompt = f"""You are a SQL performance expert.

Review and:
1. Suggest optimizations
2. Provide a revised version
3. Explain your improvements

SQL Query:
{sql_query}
"""
    elif task == "Test":
        prompt = f"""You are a SQL testing expert.

Generate:
- Sample rows per table
- Expected result set
- Notes justifying results

SQL Query:
{sql_query}
"""

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
