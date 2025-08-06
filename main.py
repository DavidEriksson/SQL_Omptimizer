import streamlit as st
import openai
import tiktoken
from datetime import datetime, timedelta
import yaml
import streamlit_authenticator as stauth
import os
from pathlib import Path

# === Secrets ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]  # List of admin emails
COOKIE_KEY = st.secrets["COOKIE_KEY"]

USERS_FILE = "users.yaml"

# === Load users.yaml safely ===
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
        yaml.dump({
            "credentials": {
                "usernames": {}
            },
            "cookie": {
                "expiry_days": 30,
                "key": st.secrets["COOKIE_KEY"],
                "name": "sql_optimizer_login"
            },
            "preauthorized": {
                "emails": []
            }
        }, f)

with open(USERS_FILE, "r") as f:
    config = yaml.safe_load(f)

# Ensure structure exists (even if file is empty or malformed)
if not config:
    config = {}
if "credentials" not in config:
    config["credentials"] = {"usernames": {}}
if "cookie" not in config:
    config["cookie"] = {
        "expiry_days": 30,
        "key": st.secrets["COOKIE_KEY"],
        "name": "sql_optimizer_login"
    }
if "preauthorized" not in config:
    config["preauthorized"] = {"emails": []}

authenticator = stauth.Authenticate(
    config,
    cookie_name="sql_optimizer_login",
    key=COOKIE_KEY,
    cookie_expiry_days=30
)

# === UI: Login/Register ===
st.set_page_config(page_title="SQL Optimizer AI", layout="centered")

# Show Login/Register buttons
if "authentication_status" not in st.session_state:
    login_placeholder = st.empty()
    with login_placeholder.container():
        col1, col2 = st.columns([1, 1])
        if col1.button("🔐 Logga in"):
            st.session_state.show_login = True
        if col2.button("🆕 Registrera dig"):
            st.session_state.show_register = True

if st.session_state.get("show_login"):
    name, authentication_status, username = authenticator.login("Logga in", "main")
    if authentication_status:
        st.success(f"👋 Välkommen {name}!")
    elif authentication_status is False:
        st.error("❌ Fel användarnamn eller lösenord")
    elif authentication_status is None:
        st.warning("⚠️ Ange inloggningsuppgifter")

if st.session_state.get("show_register"):
    with st.form("register_form", clear_on_submit=True):
        st.subheader("Registrera ny användare")
        email = st.text_input("E-post")
        name = st.text_input("Fullständigt namn")
        password = st.text_input("Lösenord", type="password")
        submitted = st.form_submit_button("Skapa konto")
        if submitted:
            if email in config["credentials"]["usernames"]:
                st.error("Användaren finns redan.")
            else:
                hashed_pw = stauth.Hasher([password]).generate()[0]
                config["credentials"]["usernames"][email] = {
                    "name": name,
                    "password": hashed_pw
                }
                with users_file.open("w") as f:
                    yaml.dump(config, f)
                st.success("✅ Konto skapat! Klicka på 'Logga in' för att logga in.")
                st.session_state.show_register = False

# === Stop if not authenticated ===
if "authentication_status" not in st.session_state or not st.session_state.authentication_status:
    st.stop()

# === Admin check ===
email = st.session_state.username
is_admin = email in ADMINS

# === Session setup ===
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)
if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False

# === Reset timer ===
if datetime.now() >= st.session_state.query_reset_time:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

# === Sidebar info ===
st.sidebar.markdown(f"👤 Inloggad som: **{email}**")
if is_admin:
    st.sidebar.success("👑 Adminkonto – obegränsad användning")
else:
    st.sidebar.markdown(f"🧠 Använda queries: **{st.session_state.query_count}/5**")
    remaining = st.session_state.query_reset_time - datetime.now()
    st.sidebar.caption(f"🔄 Återställs om: {remaining.seconds//3600}h {(remaining.seconds%3600)//60}m")

if not is_admin and st.session_state.query_count >= 5:
    st.error("❌ Du har nått max antal queries. Vänta tills återställning.")
    st.stop()

# === Input ===
st.title("SQL Optimizer")
st.markdown("---")
st.subheader("Klistra in din SQL-kod")
sql_query = st.text_area("SQL Code", height=200, placeholder="Paste SQL here...")
task = st.selectbox("Vad vill du göra?", ["Explain", "Detect Issues", "Optimize", "Test"])

model = "gpt-4o-mini"
temperature = 0.3
max_tokens = 1500
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def estimate_tokens(text):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

# === Run analysis ===
if st.button("Analysera"):
    if not sql_query.strip():
        st.error("❌ Klistra in en SQL-fråga.")
    else:
        if not is_admin:
            st.session_state.query_count += 1
        st.session_state.run_analysis = True
        st.rerun()

if st.session_state.run_analysis:
    templates = {
        "Explain": f"""
You are an expert SQL instructor.

Explain this SQL query step-by-step, including:
- The purpose of the query
- What each clause does
- The role of each table and join
- Any assumptions about the data

SQL Query:
{sql_query}
""",
        "Detect Issues": f"""
You are a senior SQL reviewer.

Analyze this SQL and list:
- Performance problems
- Bad practices
- Logical issues
- Suggestions

SQL Query:
{sql_query}
""",
        "Optimize": f"""
You are a SQL performance expert.

1. Suggest optimizations
2. Rewrite the query
3. Explain your changes

SQL Query:
{sql_query}
""",
        "Test": f"""
Generate:
- Sample data for each table
- Expected result set
- Notes explaining logic

SQL Query:
{sql_query}
"""
    }

    prompt = templates[task]

    with st.spinner("🔍 Bearbetar din SQL..."):
        try:
            tokens = estimate_tokens(prompt)
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )
            reply = response.choices[0].message.content
            st.success("✅ Klar!")
            st.markdown("### Resultat")
            st.markdown(reply)
            st.caption(f"🔢 Tokens: {tokens} • Modell: {model}")
            st.download_button("📋 Kopiera resultat", reply, file_name="sql_analysis.txt")
        except Exception as e:
            st.error(f"Fel: {str(e)}")

    st.session_state.run_analysis = False
