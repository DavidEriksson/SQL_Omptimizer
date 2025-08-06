import streamlit as st
import openai
import tiktoken
from datetime import datetime, timedelta
import yaml
import os
import streamlit_authenticator as stauth

# === Ladda nycklar och admins ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
COOKIE_KEY = st.secrets["COOKIE_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]

# === Skapa users.yaml om den inte finns ===
USERS_FILE = "users.yaml"
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        yaml.dump({
            "credentials": {
                "usernames": {}
            },
            "cookie": {
                "expiry_days": 30,
                "key": COOKIE_KEY,
                "name": "sql_optimizer_login"
            },
            "preauthorized": {
                "emails": []
            }
        }, f)

# === Ladda konfiguration från users.yaml ===
with open(USERS_FILE) as file:
    config = yaml.safe_load(file)

# === Autentisering ===
authenticator = stauth.Authenticate(
    config,
    cookie_name="sql_optimizer_login",
    key=COOKIE_KEY,
    cookie_expiry_days=30
)

# === SIDBAR - Inloggningsknapp ===
with st.sidebar:
    login_button = st.button("🔐 Logga in")
    register_button = st.button("📝 Registrera dig")

# === Visa inloggning om över 5 queries eller via knapp ===
show_login = (
    st.session_state.get("query_count", 0) >= 5
    or login_button
    or register_button
)

# === Inloggning ===
if show_login:
    if register_button:
        try:
            email, username, name, password = authenticator.register_user(preauthorization=False)
            if email and username and password:
                with open(USERS_FILE, "w") as file:
                    yaml.dump(config, file)
                st.success("Registrering lyckades. Du kan nu logga in.")
                st.stop()
        except Exception as e:
            st.error(f"Registrering misslyckades: {e}")
            st.stop()

    name, auth_status, username = authenticator.login("Logga in", "main")
    if auth_status is False:
        st.error("Felaktiga inloggningsuppgifter.")
        st.stop()
    elif auth_status is None:
        st.warning("Vänligen logga in.")
        st.stop()
    else:
        email = config["credentials"]["usernames"][username]["email"]
        is_admin = email in ADMIN_EMAILS
else:
    # === Om inte inloggad (än) ===
    name = "Guest"
    email = None
    is_admin = False

# === Session & Begränsning ===
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)
if datetime.now() >= st.session_state.query_reset_time:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)
if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False

# === UI ===
st.set_page_config(page_title="SQL Optimizer AI", layout="centered")
st.title("SQL Optimizer")
st.success(f"👋 Welcome {name}")
if is_admin:
    st.sidebar.success("👑 Admin Account (Unlimited)")
else:
    st.sidebar.info("👤 Standard Account")
    st.sidebar.markdown(f"Queries used: **{st.session_state.query_count}/5**")
    reset_in = st.session_state.query_reset_time - datetime.now()
    st.sidebar.caption(f"Resets in: {reset_in.seconds // 3600}h {(reset_in.seconds % 3600) // 60}m")

# === User input ===
st.markdown("---")
st.subheader("Paste your SQL query")
sql_query = st.text_area("SQL Code", height=200, placeholder="Paste SQL here...")
task = st.selectbox("What do you want to do?", ["Explain", "Detect Issues", "Optimize", "Test"])

model = "gpt-4o-mini"
temperature = 0.3
max_tokens = 1500
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# === Token estimation ===
def estimate_tokens(text):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

# === Kör-knapp ===
if st.button("Run"):
    if not sql_query.strip():
        st.error("❌ Please enter a SQL query.")
    elif not is_admin and st.session_state.query_count >= 5:
        st.error("❌ Query limit reached. Please log in.")
    else:
        if not is_admin:
            st.session_state.query_count += 1
        st.session_state.run_analysis = True
        st.experimental_rerun()

# === GPT-anrop ===
if st.session_state.run_analysis:
    prompts = {
        "Explain": f"""You are an expert SQL instructor.

Explain this SQL query step-by-step, including:
- The purpose of the query
- What each clause does
- The role of each table and join
- Any assumptions about the data

SQL Query:
{sql_query}""",
        "Detect Issues": f"""You are a senior SQL code reviewer.

Analyze the following SQL query and list:
- Performance problems
- Poor practices
- Logical issues
- Suggestions for improvement

SQL Query:
{sql_query}""",
        "Optimize": f"""You are a SQL performance expert.

Review the query below and:
1. Suggest how to optimize it
2. Provide a revised version
3. Explain why your changes help

SQL Query:
{sql_query}""",
        "Test": f"""You are a SQL testing expert.

Generate:
- 3 to 5 rows of sample data for each table used
- Expected result set based on the query
- Brief notes on how the data satisfies the query logic

SQL Query:
{sql_query}"""
    }

    prompt = prompts[task]
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
