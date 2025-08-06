import streamlit as st
import streamlit_authenticator as stauth
import yaml
import os
from datetime import datetime, timedelta
import openai
import tiktoken

# === Hämta hemligheter från Streamlit secrets ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
COOKIE_KEY = st.secrets["COOKIE_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]

# === Kontrollera och ladda users.yaml ===
users_file = "users.yaml"
if not os.path.exists(users_file):
    with open(users_file, "w") as f:
        yaml.safe_dump({
            "credentials": {"usernames": {}},
            "cookie": {"expiry_days": 30},
            "preauthorized": {"emails": []}
        }, f)

# Ladda konfigurationen
with open(users_file, "r") as file:
    config = yaml.safe_load(file)

# Fixa om nycklar saknas
if "credentials" not in config:
    config["credentials"] = {"usernames": {}}
if "usernames" not in config["credentials"]:
    config["credentials"]["usernames"] = {}
if "cookie" not in config:
    config["cookie"] = {"expiry_days": 30}
if "preauthorized" not in config:
    config["preauthorized"] = {"emails": []}

# === Init autentisering ===
authenticator = stauth.Authenticate(
    config,
    cookie_name="sql_optimizer_login",
    key=COOKIE_KEY,
    cookie_expiry_days=30
)

# === Välj inloggningsläge ===
auth_mode = st.sidebar.radio("Konto", ("Logga in", "Registrera"))

if auth_mode == "Registrera":
    try:
        email, username, password = authenticator.register_user(preauthorization=False)
        if email:
            with open(users_file, "w") as f:
                yaml.dump(config, f)
            st.success("✅ Användare registrerad. Logga in nedan.")
    except Exception as e:
        st.error(f"Registreringsfel: {e}")

# === Logga in ===
name, authentication_status, username = authenticator.login("Logga in", "main")

if not authentication_status:
    st.stop()

# === Inloggad ===
email = username
is_admin = email in ADMIN_EMAILS

authenticator.logout("Logga ut", "sidebar")

# === UI Setup ===
st.set_page_config(page_title="SQL Optimizer AI", layout="centered")
st.title("SQL Optimizer")
st.success(f"👋 Välkommen {name} ({email})")
st.sidebar.markdown("")

if is_admin:
    st.sidebar.success("👑 Admin-konto (Obegränsat)")
else:
    st.sidebar.info("👤 Standardanvändare")

# === Session state hantering ===
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

if datetime.now() >= st.session_state.query_reset_time:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

if not is_admin:
    st.sidebar.markdown("### 🔒 Användningsgräns")
    st.sidebar.markdown(f"Queries used: **{st.session_state.query_count}/5**")
    reset_in = st.session_state.query_reset_time - datetime.now()
    st.sidebar.caption(f"Återställs om: {reset_in.seconds // 3600}h {(reset_in.seconds % 3600) // 60}m")

# === Användarinput ===
st.markdown("---")
st.subheader("Klistra in din SQL-fråga")
sql_query = st.text_area("SQL-kod", height=200, placeholder="Klistra in din SQL här...")
task = st.selectbox("Vad vill du göra?", ["Explain", "Detect Issues", "Optimize", "Test"])
model = "gpt-4o-mini"
temperature = 0.3
max_tokens = 1500
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def estimate_tokens(text):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

if "run_analysis" not in st.session_state:
    st.session_state.run_analysis = False

# === Kör-knapp ===
if st.button("Kör"):
    if not sql_query.strip():
        st.error("❌ Ange en SQL-fråga.")
    elif not is_admin and st.session_state.query_count >= 5:
        st.error("❌ Du har nått gränsen. Vänta på återställning.")
    else:
        if not is_admin:
            st.session_state.query_count += 1
        st.session_state.run_analysis = True
        st.rerun()

# === GPT-anrop ===
if st.session_state.run_analysis:
    prompts = {
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

    with st.spinner("🔍 Analyserar SQL..."):
        try:
            prompt = prompts[task]
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
            st.error(f"Fel: {e}")

    st.session_state.run_analysis = False
