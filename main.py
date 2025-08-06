import streamlit as st
import openai
import tiktoken
from datetime import datetime, timedelta
import sqlite3
import bcrypt
import pandas as pd

# === Load from Streamlit Secrets ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]  # list of admin emails

# === Page Configuration ===
st.set_page_config(
    page_title="SQL Optimizer AI",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# === Custom CSS ===
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 2rem 0;
        margin: -1rem -1rem 2rem -1rem;
        text-align: center;
        color: white;
        border-radius: 0 0 20px 20px;
    }
    
    .metric-container {
        background: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #667eea;
        margin: 0.5rem 0;
    }
    
    .status-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        text-align: center;
        margin: 1rem 0;
    }
    
    .query-container {
        background: #f8f9fa;
        padding: 2rem;
        border-radius: 15px;
        border: 1px solid #e9ecef;
        margin: 1rem 0;
    }
    
    .sidebar .element-container {
        margin-bottom: 1rem;
    }
    
    .analytics-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-top: 4px solid #667eea;
        margin-bottom: 1rem;
    }
    
    .nav-button {
        width: 100%;
        margin: 0.2rem 0;
        padding: 0.5rem 1rem;
        background: #667eea;
        color: white;
        border: none;
        border-radius: 8px;
        text-align: left;
    }
    
    /* Fix tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding: 10px 20px;
        background-color: #f0f2f6;
        border-radius: 10px;
        color: #262730;
        border: none;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background-color: #667eea !important;
        color: white !important;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #e0e2e6;
        color: #262730;
    }
    
    .stTabs [aria-selected="true"]:hover {
        background-color: #5a6fd8 !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

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

# Check if we need to add the admin column or rename is_admin to admin
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

if 'is_admin' in column_names and 'admin' not in column_names:
    cursor.execute('ALTER TABLE users RENAME COLUMN is_admin TO admin')
    conn.commit()
elif 'admin' not in column_names and 'is_admin' not in column_names:
    cursor.execute('ALTER TABLE users ADD COLUMN admin BOOLEAN DEFAULT 0')
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

def log_query(user_email, task_type, query_length, tokens_used=None, success=True, error_message=None):
    cursor.execute('''
    INSERT INTO query_logs (user_email, task_type, query_length, tokens_used, success, error_message)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_email, task_type, query_length, tokens_used, success, error_message))
    conn.commit()

def get_analytics_data():
    analytics = {}
    
    cursor.execute('SELECT COUNT(*) FROM query_logs')
    analytics['total_queries'] = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM query_logs WHERE success = 1')
    successful_queries = cursor.fetchone()[0]
    analytics['success_rate'] = (successful_queries / analytics['total_queries'] * 100) if analytics['total_queries'] > 0 else 0
    
    cursor.execute('SELECT task_type, COUNT(*) FROM query_logs GROUP BY task_type ORDER BY COUNT(*) DESC')
    analytics['queries_by_task'] = cursor.fetchall()
    
    cursor.execute('''
    SELECT ql.user_email, u.name, COUNT(*) as query_count 
    FROM query_logs ql 
    LEFT JOIN users u ON ql.user_email = u.email 
    GROUP BY ql.user_email 
    ORDER BY query_count DESC 
    LIMIT 10
    ''')
    analytics['top_users'] = cursor.fetchall()
    
    cursor.execute('''
    SELECT DATE(timestamp) as date, COUNT(*) as queries 
    FROM query_logs 
    WHERE timestamp >= datetime('now', '-30 days')
    GROUP BY DATE(timestamp) 
    ORDER BY date DESC
    ''')
    analytics['daily_activity'] = cursor.fetchall()
    
    cursor.execute('SELECT AVG(query_length) FROM query_logs')
    avg_length = cursor.fetchone()[0]
    analytics['avg_query_length'] = round(avg_length, 0) if avg_length else 0
    
    cursor.execute('SELECT SUM(tokens_used) FROM query_logs WHERE tokens_used IS NOT NULL')
    total_tokens = cursor.fetchone()[0]
    analytics['total_tokens'] = total_tokens if total_tokens else 0
    
    cursor.execute('''
    SELECT user_email, task_type, error_message, timestamp 
    FROM query_logs 
    WHERE success = 0 
    ORDER BY timestamp DESC 
    LIMIT 10
    ''')
    analytics['recent_errors'] = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    analytics['total_users'] = cursor.fetchone()[0]
    
    cursor.execute('''
    SELECT COUNT(DISTINCT user_email) 
    FROM query_logs 
    WHERE timestamp >= datetime('now', '-7 days')
    ''')
    analytics['active_users_7d'] = cursor.fetchone()[0]
    
    return analytics

def get_analytics_data_cached(force_refresh=False):
    now = datetime.now()
    
    if (force_refresh or 
        st.session_state.last_analytics_update is None or 
        now - st.session_state.last_analytics_update > timedelta(seconds=30)):
        
        analytics = get_analytics_data()
        st.session_state.cached_analytics = analytics
        st.session_state.last_analytics_update = now
        return analytics, True
    else:
        return st.session_state.cached_analytics, False

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
if "last_analytics_update" not in st.session_state:
    st.session_state.last_analytics_update = None
if "cached_analytics" not in st.session_state:
    st.session_state.cached_analytics = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"

# === Header ===
st.markdown("""
<div class="main-header">
    <h1>🔍 SQL Optimizer AI</h1>
    <p>Analyze, optimize, and understand your SQL queries with AI-powered insights</p>
</div>
""", unsafe_allow_html=True)

# === Login/Register UI ===
if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### Welcome to SQL Optimizer")
        
        auth_tab1, auth_tab2 = st.tabs(["🔑 Login", "📝 Register"])
        
        with auth_tab1:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="Enter your email")
                password = st.text_input("Password", type="password", placeholder="Enter your password")
                login_button = st.form_submit_button("🚀 Login", use_container_width=True)

            if login_button:
                user = get_user(email)
                if user and verify_password(user[2], password):
                    st.session_state.logged_in = True
                    st.session_state.user_email = email
                    if len(user) > 3:
                        st.session_state.is_admin = bool(user[3]) if user[3] is not None else False
                    else:
                        st.session_state.is_admin = False
                    st.rerun()
                else:
                    st.error("❌ Invalid email or password")

        with auth_tab2:
            with st.form("register_form"):
                new_email = st.text_input("Email", placeholder="Enter your email")
                new_name = st.text_input("Full Name", placeholder="Enter your full name")
                new_password = st.text_input("Password", type="password", placeholder="Create a password")
                register_button = st.form_submit_button("✨ Create Account", use_container_width=True)

            if register_button:
                if get_user(new_email):
                    st.error("❌ Email already exists")
                else:
                    add_user(new_email, new_name, new_password)
                    st.success("✅ Account created successfully! Please log in.")

        # Add some info cards
        st.markdown("---")
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.markdown("""
            <div class="metric-container">
                <h4>🔍 Analyze</h4>
                <p>Get detailed explanations of your SQL queries</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_info2:
            st.markdown("""
            <div class="metric-container">
                <h4>⚡ Optimize</h4>
                <p>Improve query performance with AI suggestions</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_info3:
            st.markdown("""
            <div class="metric-container">
                <h4>🧪 Test</h4>
                <p>Generate test data and validate your queries</p>
            </div>
            """, unsafe_allow_html=True)

    st.stop()

# === Sidebar Navigation ===
with st.sidebar:
    st.markdown(f"""
    <div class="status-card">
        <h3>👋 Welcome</h3>
        <p><strong>{st.session_state.user_email}</strong></p>
        <p>{"👑 Admin Account" if st.session_state.is_admin else "👤 Standard User"}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### 🧭 Navigation")
    
    # Navigation buttons
    if st.button("🏠 Home", key="nav_home", use_container_width=True):
        st.session_state.current_page = "Home"
        st.rerun()
    
    if st.button("🔍 SQL Optimizer", key="nav_optimizer", use_container_width=True):
        st.session_state.current_page = "Optimizer"
        st.rerun()
    
    if st.session_state.is_admin:
        if st.button("📊 Analytics", key="nav_analytics", use_container_width=True):
            st.session_state.current_page = "Analytics"
            st.rerun()
        
        if st.button("👥 User Management", key="nav_users", use_container_width=True):
            st.session_state.current_page = "Users"
            st.rerun()
    
    st.markdown("---")
    
    # Usage information for non-admin users
    if not st.session_state.is_admin:
        # Reset query count if necessary
        if datetime.now() >= st.session_state.query_reset_time:
            st.session_state.query_count = 0
            st.session_state.query_reset_time = datetime.now() + timedelta(hours=24)
        
        st.markdown("### 📊 Usage")
        progress = st.session_state.query_count / 5
        st.progress(progress)
        st.markdown(f"**{st.session_state.query_count}/5** queries used today")
        
        reset_in = st.session_state.query_reset_time - datetime.now()
        hours = reset_in.seconds // 3600
        minutes = (reset_in.seconds % 3600) // 60
        st.caption(f"⏰ Resets in: {hours}h {minutes}m")
        
        if st.session_state.query_count >= 5:
            st.error("❌ Daily limit reached")
    else:
        st.success("♾️ Unlimited queries")
    
    st.markdown("---")
    
    # Settings
    st.markdown("### ⚙️ Settings")
    if st.button("🚪 Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.session_state.is_admin = False
        st.session_state.current_page = "Home"
        st.rerun()

# === Main Content Area ===
if st.session_state.current_page == "Home":
    # Dashboard/Home page
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("## 🎯 Quick Start")
        
        # Quick actions
        col_action1, col_action2 = st.columns(2)
        
        with col_action1:
            if st.button("🔍 Start Analyzing SQL", use_container_width=True, type="primary"):
                st.session_state.current_page = "Optimizer"
                st.rerun()
        
        with col_action2:
            if st.session_state.is_admin and st.button("📊 View Analytics", use_container_width=True):
                st.session_state.current_page = "Analytics"
                st.rerun()
        
        # Recent activity if available
        st.markdown("## 📈 Recent Activity")
        cursor.execute('''
        SELECT task_type, timestamp 
        FROM query_logs 
        WHERE user_email = ?
        ORDER BY timestamp DESC 
        LIMIT 5
        ''', (st.session_state.user_email,))
        recent_activity = cursor.fetchall()
        
        if recent_activity:
            for activity in recent_activity:
                task, timestamp = activity
                st.markdown(f"- 🔹 **{task}** query on {timestamp}")
        else:
            st.info("No recent activity. Start by analyzing your first SQL query!")
    
    with col2:
        st.markdown("## 📊 Your Stats")
        
        # User's personal stats
        cursor.execute('SELECT COUNT(*) FROM query_logs WHERE user_email = ?', (st.session_state.user_email,))
        user_queries = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM query_logs WHERE user_email = ? AND success = 1', (st.session_state.user_email,))
        user_success = cursor.fetchone()[0]
        
        success_rate = (user_success / user_queries * 100) if user_queries > 0 else 0
        
        st.metric("Total Queries", user_queries)
        st.metric("Success Rate", f"{success_rate:.1f}%")
        
        if not st.session_state.is_admin:
            st.metric("Daily Remaining", 5 - st.session_state.query_count)

elif st.session_state.current_page == "Optimizer":
    # SQL Optimizer page
    st.markdown("## 🔍 SQL Query Optimizer")
    
    # Main optimizer interface
    st.markdown("""
    <div class="query-container">
    """, unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        sql_query = st.text_area(
            "SQL Query", 
            height=300, 
            placeholder="Paste your SQL query here...\n\nExample:\nSELECT u.name, COUNT(o.id) as order_count\nFROM users u\nLEFT JOIN orders o ON u.id = o.user_id\nGROUP BY u.name\nORDER BY order_count DESC;",
            help="Enter your SQL query to analyze, optimize, or get explanations"
        )
    
    with col2:
        task = st.selectbox(
            "Analysis Type",
            ["Explain", "Optimize", "Detect Issues", "Test"],
            help="Choose what you want to do with your SQL query"
        )
        
        # Task descriptions
        task_descriptions = {
            "Explain": "🔍 Get a detailed step-by-step explanation",
            "Optimize": "⚡ Improve performance and efficiency", 
            "Detect Issues": "🔎 Find problems and bad practices",
            "Test": "🧪 Generate test data and expected results"
        }
        
        st.info(task_descriptions[task])
        
        analyze_button = st.button(
            "🚀 Analyze Query", 
            use_container_width=True, 
            type="primary",
            disabled=(not st.session_state.is_admin and st.session_state.query_count >= 5)
        )
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Process the query
    if analyze_button:
        if not sql_query.strip():
            st.error("❌ Please enter a SQL query.")
        elif not st.session_state.is_admin and st.session_state.query_count >= 5:
            st.error("❌ Daily query limit reached. Limit resets in 24 hours.")
        else:
            if not st.session_state.is_admin:
                st.session_state.query_count += 1
            
            # GPT Analysis
            model = "gpt-4o-mini"
            temperature = 0.3
            max_tokens = 1500
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            def estimate_tokens(text):
                enc = tiktoken.encoding_for_model(model)
                return len(enc.encode(text))
            
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
            
            with st.spinner("🔍 Analyzing your SQL query..."):
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
                    
                    # Results in a nice container
                    st.markdown("### 📋 Analysis Results")
                    st.markdown(f"**Task:** {task}")
                    st.markdown("---")
                    st.markdown(reply)
                    
                    # Footer info
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.caption(f"🔢 Tokens used: {token_estimate}")
                    with col_info2:
                        st.caption(f"🤖 Model: {model}")
                    with col_info3:
                        st.download_button("📋 Download Results", reply, file_name=f"sql_analysis_{task.lower()}.txt")
                    
                except Exception as e:
                    # Log failed query
                    log_query(
                        user_email=st.session_state.user_email,
                        task_type=task,
                        query_length=len(sql_query),
                        success=False,
                        error_message=str(e)
                    )
                    
                    st.error(f"❌ Error: {str(e)}")

elif st.session_state.current_page == "Analytics" and st.session_state.is_admin:
    # Analytics Dashboard
    st.markdown("## 📊 Analytics Dashboard")
    
    # Refresh controls
    col_refresh1, col_refresh2, col_refresh3, col_refresh4 = st.columns([1, 1, 1, 2])
    
    with col_refresh1:
        manual_refresh = st.button("🔄 Refresh", use_container_width=True)
    
    with col_refresh2:
        auto_refresh = st.toggle("Auto-refresh")
    
    with col_refresh3:
        refresh_rate = st.selectbox("Rate (s)", [15, 30, 60], index=1)
    
    # Get analytics data
    analytics_data, is_fresh = get_analytics_data_cached(force_refresh=manual_refresh)
    
    # Show data freshness
    with col_refresh4:
        if st.session_state.last_analytics_update:
            last_update = st.session_state.last_analytics_update
            age_seconds = (datetime.now() - last_update).total_seconds()
            
            if is_fresh:
                st.success(f"🆕 Just updated!")
            elif age_seconds < 60:
                st.info(f"📊 Updated {int(age_seconds)}s ago")
            else:
                st.warning(f"📊 Updated {int(age_seconds/60)}m ago")
    
    # Auto-refresh logic
    if auto_refresh:
        if st.session_state.last_analytics_update:
            age = (datetime.now() - st.session_state.last_analytics_update).total_seconds()
            if age >= refresh_rate:
                st.rerun()
    
    # Key Metrics
    st.markdown("### 📈 Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="👥 Total Users",
            value=analytics_data['total_users'],
            delta=f"{analytics_data['active_users_7d']} active (7d)"
        )
    
    with col2:
        st.metric(
            label="🔍 Total Queries", 
            value=analytics_data['total_queries'],
            delta=f"{analytics_data['success_rate']:.1f}% success rate"
        )
    
    with col3:
        estimated_cost = (analytics_data['total_tokens'] / 1000) * 0.000150
        st.metric(
            label="💰 API Costs",
            value=f"${estimated_cost:.3f}",
            delta=f"{analytics_data['total_tokens']:,} tokens"
        )
    
    with col4:
        popular_task = analytics_data['queries_by_task'][0][0] if analytics_data['queries_by_task'] else "None"
        st.metric(
            label="🔥 Most Popular Task",
            value=popular_task,
            delta=f"Avg {analytics_data['avg_query_length']} chars/query"
        )
    
    # Detailed Analytics
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Usage Trends", "👥 User Activity", "🔧 Task Types", "❌ Errors"])
    
    with tab1:
        col_chart1, col_chart2 = st.columns([2, 1])
        
        with col_chart1:
            st.markdown("#### Daily Query Volume (Last 30 Days)")
            if analytics_data['daily_activity']:
                df_daily = pd.DataFrame(analytics_data['daily_activity'], columns=['Date', 'Queries'])
                st.bar_chart(df_daily.set_index('Date'), use_container_width=True)
            else:
                st.info("No data available yet")
        
        with col_chart2:
            st.markdown("#### Live Activity Feed")
            cursor.execute('''
            SELECT user_email, task_type, timestamp 
            FROM query_logs 
            WHERE timestamp >= datetime('now', '-2 hours')
            ORDER BY timestamp DESC 
            LIMIT 8
            ''')
            recent_queries = cursor.fetchall()
            
            if recent_queries:
                for query in recent_queries:
                    email, task, timestamp = query
                    query_time = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    time_ago = datetime.now() - query_time
                    
                    if time_ago.seconds < 60:
                        time_str = f"{time_ago.seconds}s ago"
                    elif time_ago.seconds < 3600:
                        time_str = f"{time_ago.seconds//60}m ago"
                    else:
                        time_str = f"{time_ago.seconds//3600}h ago"
                    
                    st.markdown(f"🔸 **{email}** used *{task}* {time_str}")
            else:
                st.info("No recent activity")
    
    with tab2:
        if analytics_data['top_users']:
            df_users = pd.DataFrame(analytics_data['top_users'], columns=['Email', 'Name', 'Query Count'])
            st.dataframe(df_users, use_container_width=True)
        else:
            st.info("No user data available yet")
    
    with tab3:
        col_task1, col_task2 = st.columns([1, 1])
        
        with col_task1:
            if analytics_data['queries_by_task']:
                df_tasks = pd.DataFrame(analytics_data['queries_by_task'], columns=['Task Type', 'Count'])
                st.bar_chart(df_tasks.set_index('Task Type'), use_container_width=True)
        
        with col_task2:
            if analytics_data['queries_by_task']:
                st.dataframe(df_tasks, use_container_width=True)
            else:
                st.info("No task data available yet")
    
    with tab4:
        if analytics_data['recent_errors']:
            df_errors = pd.DataFrame(analytics_data['recent_errors'], 
                                   columns=['User Email', 'Task Type', 'Error', 'Timestamp'])
            st.dataframe(df_errors, use_container_width=True)
        else:
            st.success("🎉 No recent errors!")

elif st.session_state.current_page == "Users" and st.session_state.is_admin:
    # User Management page
    st.markdown("## 👥 User Management")
    
    tab1, tab2, tab3 = st.tabs(["📋 All Users", "⚙️ Manage Users", "📊 User Analytics"])
    
    with tab1:
        st.markdown("#### All Registered Users")
        cursor.execute('SELECT email, name, admin FROM users')
        users = cursor.fetchall()
        
        if users:
            df = pd.DataFrame(users, columns=['Email', 'Name', 'Admin Status'])
            df['Admin Status'] = df['Admin Status'].map({1: '👑 Admin', 0: '👤 User', None: '👤 User'})
            st.dataframe(df, use_container_width=True)
            st.caption(f"Total users: {len(users)}")
        else:
            st.info("No users found")
    
    with tab2:
        col_manage1, col_manage2 = st.columns(2)
        
        with col_manage1:
            st.markdown("#### 👑 Grant Admin Access")
            cursor.execute('SELECT email, name FROM users WHERE admin = 0 OR admin IS NULL')
            regular_users = cursor.fetchall()
            
            if regular_users:
                user_options = [f"{user[1]} ({user[0]})" for user in regular_users]
                selected_user_idx = st.selectbox("Select user:", range(len(user_options)), 
                                                format_func=lambda x: user_options[x])
                selected_email = regular_users[selected_user_idx][0]
                
                if st.button("🚀 Grant Admin Access", use_container_width=True, type="primary"):
                    cursor.execute('UPDATE users SET admin = 1 WHERE email = ?', (selected_email,))
                    conn.commit()
                    st.success(f"✅ {selected_email} is now an admin!")
                    st.rerun()
            else:
                st.info("All users are already admins")
        
        with col_manage2:
            st.markdown("#### 🗑️ Remove User")
            cursor.execute('SELECT email, name FROM users')
            all_users = cursor.fetchall()
            
            if len(all_users) > 1:
                user_options_delete = [f"{user[1]} ({user[0]})" for user in all_users]
                selected_user_delete_idx = st.selectbox("Select user to delete:", range(len(user_options_delete)), 
                                                       format_func=lambda x: user_options_delete[x], key="delete_user")
                selected_email_delete = all_users[selected_user_delete_idx][0]
                
                if selected_email_delete != st.session_state.user_email:
                    if st.button("🗑️ Delete User", use_container_width=True, type="secondary"):
                        cursor.execute('DELETE FROM users WHERE email = ?', (selected_email_delete,))
                        conn.commit()
                        st.success(f"✅ User {selected_email_delete} deleted!")
                        st.rerun()
                else:
                    st.error("❌ Cannot delete your own account!")
            else:
                st.info("Cannot delete users - you're the only one!")
    
    with tab3:
        st.markdown("#### 👤 Individual User Statistics")
        
        # User activity breakdown
        cursor.execute('''
        SELECT 
            u.email, u.name,
            COUNT(ql.id) as total_queries,
            SUM(CASE WHEN ql.success = 1 THEN 1 ELSE 0 END) as successful_queries,
            MAX(ql.timestamp) as last_activity
        FROM users u
        LEFT JOIN query_logs ql ON u.email = ql.user_email
        GROUP BY u.email, u.name
        ORDER BY total_queries DESC
        ''')
        
        user_stats = cursor.fetchall()
        
        if user_stats:
            for stat in user_stats:
                email, name, total, success, last_activity = stat
                success_rate = (success / total * 100) if total > 0 else 0
                
                with st.expander(f"📊 {name} ({email})"):
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    
                    with col_stat1:
                        st.metric("Total Queries", total or 0)
                    with col_stat2:
                        st.metric("Success Rate", f"{success_rate:.1f}%" if total > 0 else "N/A")
                    with col_stat3:
                        st.metric("Last Activity", last_activity or "Never")
                    
                    if total > 0:
                        # Get task breakdown for this user
                        cursor.execute('''
                        SELECT task_type, COUNT(*) as count
                        FROM query_logs 
                        WHERE user_email = ?
                        GROUP BY task_type
                        ''', (email,))
                        
                        user_tasks = cursor.fetchall()
                        if user_tasks:
                            st.markdown("**Task Breakdown:**")
                            for task, count in user_tasks:
                                st.markdown(f"- {task}: {count} queries")
        else:
            st.info("No user activity data available")

# === Footer ===
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem 0;">
    <p>🔍 SQL Optimizer AI - Powered by GPT-4o Mini</p>
    <p>Built with ❤️ using Streamlit</p>
</div>
""", unsafe_allow_html=True)