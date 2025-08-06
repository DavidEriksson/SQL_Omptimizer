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
conn = sqlite3.connect('SQLOpt_prod.db', check_same_thread=False)
cursor = conn.cursor()

# Create users table if it doesn't exist
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    password TEXT NOT NULL,
    admin BOOLEAN NULL
)
''')
conn.commit()

# === Analytics Database Setup ===
cursor.execute('''
CREATE TABLE IF NOT EXISTS query_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    task_type TEXT NOT NULL,
    query_length INTEGER NOT NULL,
    tokens_used INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_email) REFERENCES users(email)
)
''')
conn.commit()

def log_query(user_email, task_type, query_length, tokens_used=None, success=True, error_message=None):
    """Log a query execution to the analytics table"""
    cursor.execute('''
    INSERT INTO query_logs (user_email, task_type, query_length, tokens_used, success, error_message)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_email, task_type, query_length, tokens_used, success, error_message))
    conn.commit()

def get_analytics_data():
    """Get various analytics data for the dashboard"""
    analytics = {}
    
    # Total queries
    cursor.execute('SELECT COUNT(*) FROM query_logs')
    analytics['total_queries'] = cursor.fetchone()[0]
    
    # Success rate
    cursor.execute('SELECT COUNT(*) FROM query_logs WHERE success = 1')
    successful_queries = cursor.fetchone()[0]
    analytics['success_rate'] = (successful_queries / analytics['total_queries'] * 100) if analytics['total_queries'] > 0 else 0
    
    # Queries by task type
    cursor.execute('SELECT task_type, COUNT(*) FROM query_logs GROUP BY task_type ORDER BY COUNT(*) DESC')
    analytics['queries_by_task'] = cursor.fetchall()
    
    # Queries by user (top 10)
    cursor.execute('''
    SELECT ql.user_email, u.name, COUNT(*) as query_count 
    FROM query_logs ql 
    LEFT JOIN users u ON ql.user_email = u.email 
    GROUP BY ql.user_email 
    ORDER BY query_count DESC 
    LIMIT 10
    ''')
    analytics['top_users'] = cursor.fetchall()
    
    # Daily activity (last 30 days)
    cursor.execute('''
    SELECT DATE(timestamp) as date, COUNT(*) as queries 
    FROM query_logs 
    WHERE timestamp >= datetime('now', '-30 days')
    GROUP BY DATE(timestamp) 
    ORDER BY date DESC
    ''')
    analytics['daily_activity'] = cursor.fetchall()
    
    # Average query length
    cursor.execute('SELECT AVG(query_length) FROM query_logs')
    avg_length = cursor.fetchone()[0]
    analytics['avg_query_length'] = round(avg_length, 0) if avg_length else 0
    
    # Total tokens used
    cursor.execute('SELECT SUM(tokens_used) FROM query_logs WHERE tokens_used IS NOT NULL')
    total_tokens = cursor.fetchone()[0]
    analytics['total_tokens'] = total_tokens if total_tokens else 0
    
    # Recent errors
    cursor.execute('''
    SELECT user_email, task_type, error_message, timestamp 
    FROM query_logs 
    WHERE success = 0 
    ORDER BY timestamp DESC 
    LIMIT 10
    ''')
    analytics['recent_errors'] = cursor.fetchall()
    
    # User count
    cursor.execute('SELECT COUNT(*) FROM users')
    analytics['total_users'] = cursor.fetchone()[0]
    
    # Active users (users who made queries in last 7 days)
    cursor.execute('''
    SELECT COUNT(DISTINCT user_email) 
    FROM query_logs 
    WHERE timestamp >= datetime('now', '-7 days')
    ''')
    analytics['active_users_7d'] = cursor.fetchone()[0]
    
    return analytics

def add_user(email, name, password, is_admin=False):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor.execute('''
    INSERT INTO users (email, name, password, admin) VALUES (?, ?, ?, ?)
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
                st.rerun()
            else:
                st.error("Invalid email or password")

    st.stop()

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
    st.rerun()


# === Admin User Management ===
if st.session_state.is_admin:
    with st.expander("👑 Admin: User Management"):
        tab1, tab2 = st.tabs(["View Users", "Manage Users"])
        
        with tab1:
            st.subheader("All Users")
            cursor.execute('SELECT email, name, is_admin FROM users')
            users = cursor.fetchall()
            
            if users:
                import pandas as pd
                df = pd.DataFrame(users, columns=['Email', 'Name', 'Admin'])
                st.dataframe(df, use_container_width=True)
                st.caption(f"Total users: {len(users)}")
            else:
                st.info("No users found")
        
        with tab2:
            st.subheader("Make User Admin")
            cursor.execute('SELECT email, name FROM users WHERE is_admin = 0 OR is_admin IS NULL')
            regular_users = cursor.fetchall()
            
            if regular_users:
                user_emails = [user[0] for user in regular_users]
                selected_email = st.selectbox("Select user to make admin:", user_emails)
                
                if st.button("Grant Admin Access"):
                    cursor.execute('UPDATE users SET is_admin = 1 WHERE email = ?', (selected_email,))
                    conn.commit()
                    st.success(f"✅ {selected_email} is now an admin!")
                    st.rerun()
            else:
                st.info("All users are already admins")
            
            st.subheader("Remove User")
            cursor.execute('SELECT email, name FROM users')
            all_users = cursor.fetchall()
            
            if len(all_users) > 1:  # Don't allow deleting the last user
                user_emails_delete = [user[0] for user in all_users]
                selected_email_delete = st.selectbox("Select user to delete:", user_emails_delete)
                
                if st.button("🗑️ Delete User", type="secondary"):
                    if selected_email_delete != st.session_state.user_email:
                        cursor.execute('DELETE FROM users WHERE email = ?', (selected_email_delete,))
                        conn.commit()
                        st.success(f"✅ User {selected_email_delete} deleted!")
                        st.rerun()
                    else:
                        st.error("❌ Cannot delete your own account!")
            else:
                st.info("Cannot delete users - you're the only one!")

    
    with st.expander("📊 Analytics Dashboard", expanded=True):
        st.subheader("📈 Usage Analytics")
        
        # Get analytics data
        analytics = get_analytics_data()
        
        # Key Metrics Row
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Users", analytics['total_users'])
            st.metric("Active Users (7d)", analytics['active_users_7d'])
        
        with col2:
            st.metric("Total Queries", analytics['total_queries'])
            st.metric("Success Rate", f"{analytics['success_rate']:.1f}%")
        
        with col3:
            st.metric("Avg Query Length", f"{analytics['avg_query_length']} chars")
            st.metric("Total Tokens Used", f"{analytics['total_tokens']:,}")
        
        with col4:
            # Calculate estimated cost (GPT-4o-mini pricing)
            estimated_cost = (analytics['total_tokens'] / 1000) * 0.000150  # $0.150 per 1K tokens
            st.metric("Est. API Cost", f"${estimated_cost:.3f}")
            
            # Most popular task
            if analytics['queries_by_task']:
                popular_task = analytics['queries_by_task'][0][0]
                st.metric("Most Popular Task", popular_task)
        
        # Charts and detailed data
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Usage Trends", "👥 User Activity", "🔧 Task Types", "❌ Errors"])
        
        with tab1:
            st.subheader("Daily Query Volume (Last 30 Days)")
            if analytics['daily_activity']:
                import pandas as pd
                df_daily = pd.DataFrame(analytics['daily_activity'], columns=['Date', 'Queries'])
                st.bar_chart(df_daily.set_index('Date'))
            else:
                st.info("No data available yet")
        
        with tab2:
            st.subheader("Top Active Users")
            if analytics['top_users']:
                df_users = pd.DataFrame(analytics['top_users'], columns=['Email', 'Name', 'Query Count'])
                st.dataframe(df_users, use_container_width=True)
            else:
                st.info("No user data available yet")
        
        with tab3:
            st.subheader("Queries by Task Type")
            if analytics['queries_by_task']:
                df_tasks = pd.DataFrame(analytics['queries_by_task'], columns=['Task Type', 'Count'])
                st.bar_chart(df_tasks.set_index('Task Type'))
                st.dataframe(df_tasks, use_container_width=True)
            else:
                st.info("No task data available yet")
        
        with tab4:
            st.subheader("Recent Errors")
            if analytics['recent_errors']:
                df_errors = pd.DataFrame(analytics['recent_errors'], 
                                       columns=['User Email', 'Task Type', 'Error', 'Timestamp'])
                st.dataframe(df_errors, use_container_width=True)
            else:
                st.success("No recent errors! 🎉")

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
    elif not st.session_state.is_admin and st.session_state.query_count >= 5:
        st.error("❌ Query limit reached. Please wait for reset.")
    else:
        if not st.session_state.is_admin:
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
            
            # Log successful query
            log_query(
                user_email=st.session_state.user_email,
                task_type=task,
                query_length=len(sql_query),
                tokens_used=token_estimate,
                success=True
            )
            
            st.success("✅ Analysis complete!")
            st.markdown("### Result")
            st.markdown(reply)
            st.caption(f"🔢 Estimated tokens: {token_estimate} • Model: {model}")
            st.download_button("📋 Copy Result", reply, file_name="sql_analysis.txt")
            
        except Exception as e:
            # Log failed query
            log_query(
                user_email=st.session_state.user_email,
                task_type=task,
                query_length=len(sql_query),
                success=False,
                error_message=str(e)
            )
            
            st.error(f"Error: {str(e)}")

    st.session_state.run_analysis = False
