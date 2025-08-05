import ***REMOVED*** as st
import ***REMOVED***
import ***REMOVED***
from datetime import datetime, timedelta

# === Session state setup ===
if "query_count" not in st.session_state:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

# === Reset after 24h ===
if datetime.now() >= st.session_state.query_reset_time:
    st.session_state.query_count = 0
    st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)

# === Sidebar display ===
st.sidebar.markdown("### 🔒 Usage Limit")
st.sidebar.markdown(f"Queries used: **{st.session_state.query_count}/5**")
reset_in = st.session_state.query_reset_time - datetime.now()
hours = reset_in.seconds // 3600
minutes = (reset_in.seconds % 3600) // 60
st.sidebar.caption(f"Resets in: {hours}h {minutes}m")

# === Streamlit app setup ===
client = ***REMOVED***.OpenAI()
st.set_page_config(page_title="SQL Optimizer AI", layout="centered")
st.title("SQL Optimizer")
st.markdown("---")

# === User input ===
st.subheader("Paste your SQL query")
sql_query = st.text_area("SQL Code", height=200, placeholder="Paste SQL here...")
task = st.selectbox("What do you want to do?", ["Explain", "Detect Issues", "Optimize", "Test"])

model = "gpt-4o-mini"
temperature = 0.3
max_tokens = 1500

# === Token estimation function ===
def estimate_tokens(text):
    enc = ***REMOVED***.encoding_for_model(model)
    return len(enc.encode(text))

# === Run Button ===
if st.button("Run"):
    if not sql_query.strip():
        st.error("❌ Please enter a SQL query.")
    elif st.session_state.query_count >= 5:
        st.error("❌ Query limit reached. Please try again later.")
    else:
        # ✅ Count before OpenAI call
        st.session_state.query_count += 1

        # === Build prompt ===
        if task == "Explain":
            prompt = f"""
You are an expert SQL instructor.

Explain this SQL query step-by-step, including:
- The purpose of the query
- What each clause does
- The role of each table and join
- Any assumptions about the data

Don't talk like an AI bot.

SQL Query:
{sql_query}
"""
        elif task == "Detect Issues":
            prompt = f"""
You are a senior SQL code reviewer.

Analyze the following SQL query and list:
- Performance problems
- Poor practices
- Logical issues
- Suggestions for improvement

Don't talk like an AI bot.

SQL Query:
{sql_query}
"""
        elif task == "Optimize":
            prompt = f"""
You are a SQL performance expert.

Review the query below and:
1. Suggest how to optimize it
2. Provide a revised version
3. Explain why your changes help

Don't talk like an AI bot.

SQL Query:
{sql_query}
"""
        elif task == "Test":
            prompt = f"""
You are a SQL testing expert.

Generate:
- 3 to 5 rows of sample data for each table used
- Expected result set based on the query
- Brief notes on how the data satisfies the query logic

Don't talk like an AI bot.

SQL Query:
{sql_query}
"""

        # === OpenAI request ===
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
