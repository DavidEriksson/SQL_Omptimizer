import streamlit as st
import streamlit.components.v1
import openai
import tiktoken
from datetime import datetime, timedelta
import sqlite3
import bcrypt
import pandas as pd

# === Load from Streamlit Secrets ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]

# === Page Configuration ===
st.set_page_config(
    page_title="SQL Optimizer AI",
    page_icon="",
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
        background: #2d3748;
        color: white;
        padding: 1rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
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
        background: transparent;
        padding: 2rem;
        border-radius: 15px;
        border: 1px solid #444;
        margin: 1rem 0;
    }
    
    .stButton > button {
        width: 100%;
        margin: 0.2rem 0;
        padding: 0.5rem 1rem;
        border-radius: 8px;
        text-align: left;
        transition: all 0.2s ease;
    }
    
    div[data-testid="stSidebar"] button[kind="primary"] {
        background-color: #667eea !important;
        color: white !important;
        border: none !important;
    }
    
    div[data-testid="stSidebar"] button[kind="secondary"] {
        background-color: #4a5568 !important;
        color: #cbd5e0 !important;
        border: none !important;
    }
    
    .stTextArea textarea {
        font-family: 'Courier New', monospace !important;
        tab-size: 4 !important;
        border: 1px solid #444 !important;
        background-color: #262730 !important;
        color: #fafafa !important;
    }
    
    .stTextArea textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 2px rgba(102, 126, 234, 0.2) !important;
    }
    
    div[data-testid="stTabs"] > div[data-baseweb="tab-list"] {
        gap: 8px !important;
        background-color: transparent !important;
    }
    
    div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button[data-baseweb="tab"] {
        height: 50px !important;
        padding: 10px 20px !important;
        background-color: #f0f2f6 !important;
        border-radius: 10px !important;
        color: #262730 !important;
        border: none !important;
        font-weight: 500 !important;
        margin-right: 4px !important;
    }
    
    div[data-testid="stTabs"] > div[data-baseweb="tab-list"] button[data-baseweb="tab"][aria-selected="true"] {
        background-color: #667eea !important;
        color: white !important;
    }
</style>
""", unsafe_allow_html=True)

# === Database Setup ===
conn = sqlite3.connect('SQLOpt_prod.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    email TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    password TEXT NOT NULL,
    admin BOOLEAN NULL
)
''')

cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
column_names = [column[1] for column in columns]

if 'is_admin' in column_names and 'admin' not in column_names:
    cursor.execute('ALTER TABLE users RENAME COLUMN is_admin TO admin')
    conn.commit()
elif 'admin' not in column_names and 'is_admin' not in column_names:
    cursor.execute('ALTER TABLE users ADD COLUMN admin BOOLEAN DEFAULT 0')
    conn.commit()

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

cursor.execute('''
CREATE TABLE IF NOT EXISTS query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_email TEXT NOT NULL,
    query_text TEXT NOT NULL,
    task_type TEXT NOT NULL,
    result_text TEXT,
    is_favorite BOOLEAN DEFAULT 0,
    query_name TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_email) REFERENCES users(email)
)
''')
conn.commit()

# === Functions ===
def add_user(email, name, password, is_admin=False):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor.execute('INSERT INTO users (email, name, password, admin) VALUES (?, ?, ?, ?)', 
                   (email, name, hashed_password, is_admin))
    conn.commit()

def get_user(email):
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    return cursor.fetchone()

def verify_password(stored_password, provided_password):
    return bcrypt.checkpw(provided_password.encode(), stored_password.encode())

def log_query(user_email, task_type, query_length, tokens_used=None, success=True, error_message=None):
    cursor.execute('INSERT INTO query_logs (user_email, task_type, query_length, tokens_used, success, error_message) VALUES (?, ?, ?, ?, ?, ?)',
                   (user_email, task_type, query_length, tokens_used, success, error_message))
    conn.commit()

def save_query_to_history(user_email, query_text, task_type, result_text=None, query_name=None):
    cursor.execute('INSERT INTO query_history (user_email, query_text, task_type, result_text, query_name) VALUES (?, ?, ?, ?, ?)',
                   (user_email, query_text, task_type, result_text, query_name))
    conn.commit()
    return cursor.lastrowid

def get_user_query_history(user_email, limit=50):
    cursor.execute('''SELECT id, query_text, task_type, result_text, is_favorite, query_name, timestamp
                      FROM query_history WHERE user_email = ? ORDER BY timestamp DESC LIMIT ?''',
                   (user_email, limit))
    return cursor.fetchall()

def get_user_favorites(user_email):
    cursor.execute('''SELECT id, query_text, task_type, result_text, query_name, timestamp
                      FROM query_history WHERE user_email = ? AND is_favorite = 1 ORDER BY timestamp DESC''',
                   (user_email,))
    return cursor.fetchall()

def toggle_favorite(query_id):
    cursor.execute('SELECT is_favorite FROM query_history WHERE id = ?', (query_id,))
    current_status = cursor.fetchone()[0]
    new_status = 0 if current_status else 1
    cursor.execute('UPDATE query_history SET is_favorite = ? WHERE id = ?', (new_status, query_id))
    conn.commit()
    return new_status

def delete_query_from_history(query_id, user_email):
    cursor.execute('DELETE FROM query_history WHERE id = ? AND user_email = ?', (query_id, user_email))
    conn.commit()
    return cursor.rowcount > 0

def update_query_name(query_id, user_email, new_name):
    cursor.execute('UPDATE query_history SET query_name = ? WHERE id = ? AND user_email = ?', 
                   (new_name, query_id, user_email))
    conn.commit()
    return cursor.rowcount > 0

def format_sql(sql_query):
    if not sql_query.strip():
        return sql_query
    
    keywords = [
        'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN',
        'FULL JOIN', 'CROSS JOIN', 'ON', 'AND', 'OR', 'NOT', 'IN', 'EXISTS', 'BETWEEN',
        'LIKE', 'IS', 'NULL', 'GROUP BY', 'HAVING', 'ORDER BY', 'ASC', 'DESC', 'LIMIT',
        'OFFSET', 'UNION', 'UNION ALL', 'INTERSECT', 'EXCEPT', 'WITH', 'AS', 'CASE',
        'WHEN', 'THEN', 'ELSE', 'END', 'IF', 'DISTINCT', 'ALL', 'COUNT', 'SUM', 'AVG',
        'MIN', 'MAX', 'SUBSTRING', 'CONCAT', 'COALESCE', 'CAST', 'CONVERT', 'INSERT',
        'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER', 'TABLE', 'INDEX', 'VIEW'
    ]
    
    import re
    result = sql_query
    
    for keyword in keywords:
        pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
        result = re.sub(pattern, keyword, result, flags=re.IGNORECASE)
    
    result = re.sub(r'[ \t]+', ' ', result)
    result = re.sub(r' +\n', '\n', result)
    result = re.sub(r'\n +', '\n', result)
    result = re.sub(r' ,', ',', result)
    result = re.sub(r',([a-zA-Z0-9_])', r', \1', result)
    result = re.sub(r'\( ', '(', result)
    result = re.sub(r' \)', ')', result)
    
    return result.strip()

def get_analytics_data():
    analytics = {}
    cursor.execute('SELECT COUNT(*) FROM query_logs')
    analytics['total_queries'] = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(*) FROM query_logs WHERE success = 1')
    successful_queries = cursor.fetchone()[0]
    analytics['success_rate'] = (successful_queries / analytics['total_queries'] * 100) if analytics['total_queries'] > 0 else 0
    cursor.execute('SELECT task_type, COUNT(*) FROM query_logs GROUP BY task_type ORDER BY COUNT(*) DESC')
    analytics['queries_by_task'] = cursor.fetchall()
    cursor.execute('SELECT COUNT(*) FROM users')
    analytics['total_users'] = cursor.fetchone()[0]
    cursor.execute('SELECT COUNT(DISTINCT user_email) FROM query_logs WHERE timestamp >= datetime("now", "-7 days")')
    analytics['active_users_7d'] = cursor.fetchone()[0]
    cursor.execute('SELECT AVG(query_length) FROM query_logs')
    avg_length = cursor.fetchone()[0]
    analytics['avg_query_length'] = round(avg_length, 0) if avg_length else 0
    cursor.execute('SELECT SUM(tokens_used) FROM query_logs WHERE tokens_used IS NOT NULL')
    total_tokens = cursor.fetchone()[0]
    analytics['total_tokens'] = total_tokens if total_tokens else 0
    return analytics

def get_analytics_data_cached(force_refresh=False):
    now = datetime.now()
    if (force_refresh or st.session_state.last_analytics_update is None or 
        now - st.session_state.last_analytics_update > timedelta(seconds=30)):
        analytics = get_analytics_data()
        st.session_state.cached_analytics = analytics
        st.session_state.last_analytics_update = now
        return analytics, True
    else:
        return st.session_state.cached_analytics, False

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

# === Header ===
st.markdown("""
<div class="main-header">
    <h1>SQL Optimizer AI</h1>
    <p>Analyze, optimize, and understand your SQL queries with AI-powered insights</p>
</div>
""", unsafe_allow_html=True)

# === Login/Register ===
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
                if user and verify_password(user[2], password):
                    st.session_state.logged_in = True
                    st.session_state.user_email = email
                    if len(user) > 3:
                        st.session_state.is_admin = bool(user[3]) if user[3] is not None else False
                    else:
                        st.session_state.is_admin = False
                    st.rerun()
                else:
                    st.error("Invalid email or password")

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
                    add_user(new_email, new_name, new_password)
                    st.success("Account created successfully! Please log in.")

        st.markdown("---")
        col_info1, col_info2, col_info3 = st.columns(3)
        
        with col_info1:
            st.markdown("""
            <div class="metric-container">
                <h4>Analyze</h4>
                <p>Get detailed explanations of your SQL queries</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_info2:
            st.markdown("""
            <div class="metric-container">
                <h4>Optimize</h4>
                <p>Improve query performance with AI suggestions</p>
            </div>
            """, unsafe_allow_html=True)
        
        with col_info3:
            st.markdown("""
            <div class="metric-container">
                <h4>Test</h4>
                <p>Generate test data and validate your queries</p>
            </div>
            """, unsafe_allow_html=True)

    st.stop()

# === Sidebar ===
with st.sidebar:
    st.markdown(f"""
    <div class="status-card">
        <h3>Welcome</h3>
        <p><strong>{st.session_state.user_email}</strong></p>
        <p>{"Admin Account" if st.session_state.is_admin else "Standard User"}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("### Navigation")
    
    if st.button("Home", key="nav_home", use_container_width=True, 
                 type="primary" if st.session_state.current_page == "Home" else "secondary"):
        st.session_state.current_page = "Home"
        st.rerun()
    
    if st.button("SQL Optimizer", key="nav_optimizer", use_container_width=True,
                 type="primary" if st.session_state.current_page == "Optimizer" else "secondary"):
        st.session_state.current_page = "Optimizer"
        st.rerun()
    
    if st.button("Query History", key="nav_history", use_container_width=True,
                 type="primary" if st.session_state.current_page == "History" else "secondary"):
        st.session_state.current_page = "History"
        st.rerun()
    
    if st.session_state.is_admin:
        if st.button("Analytics", key="nav_analytics", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Analytics" else "secondary"):
            st.session_state.current_page = "Analytics"
            st.rerun()
        
        if st.button("User Management", key="nav_users", use_container_width=True,
                     type="primary" if st.session_state.current_page == "Users" else "secondary"):
            st.session_state.current_page = "Users"
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
        st.markdown("### Usage")
        st.success("Unlimited queries")
    
    st.markdown("---")
    
    st.markdown("### Settings")
    if st.button("Logout", use_container_width=True, type="secondary"):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.session_state.is_admin = False
        st.session_state.current_page = "Home"
        st.rerun()

# === Main Content ===
if st.session_state.current_page == "Home":
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("## Quick Start")
        
        col_action1, col_action2 = st.columns(2)
        
        with col_action1:
            if st.button("Start Analyzing SQL", use_container_width=True, type="primary"):
                st.session_state.current_page = "Optimizer"
                st.rerun()
        
        with col_action2:
            if st.session_state.is_admin and st.button("View Analytics", use_container_width=True):
                st.session_state.current_page = "Analytics"
                st.rerun()
        
        st.markdown("## Recent Activity")
        cursor.execute('SELECT task_type, timestamp FROM query_logs WHERE user_email = ? ORDER BY timestamp DESC LIMIT 5',
                       (st.session_state.user_email,))
        recent_activity = cursor.fetchall()
        
        if recent_activity:
            for activity in recent_activity:
                task, timestamp = activity
                st.markdown(f"- **{task}** query on {timestamp}")
        else:
            st.info("No recent activity. Start by analyzing your first SQL query!")
    
    with col2:
        st.markdown("## Your Stats")
        
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
    st.markdown("## SQL Query Optimizer")
    
    st.markdown('<div class="query-container">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        default_value = ""
        if st.session_state.selected_history_query:
            default_value = st.session_state.selected_history_query
            st.session_state.selected_history_query = None
        elif st.session_state.formatted_sql:
            default_value = st.session_state.formatted_sql
            st.session_state.formatted_sql = None
        else:
            default_value = st.session_state.current_sql_query
        
        sql_query = st.text_area(
            "SQL Query", 
            value=default_value,
            height=300, 
            placeholder="Paste your SQL query here...\n\nExample:\nSELECT u.name, COUNT(o.id) as order_count\nFROM users u\nLEFT JOIN orders o ON u.id = o.user_id\nGROUP BY u.name\nORDER BY order_count DESC;",
            help="Enter your SQL query to analyze, optimize, or get explanations",
            key="sql_input"
        )
        
        if sql_query != st.session_state.current_sql_query:
            st.session_state.current_sql_query = sql_query
        
        st.components.v1.html("""
        <script>
        function enableTabs() {
            const textarea = parent.document.querySelector('textarea[aria-label="SQL Query"]');
            if (textarea) {
                textarea.addEventListener('keydown', function(e) {
                    if (e.key === 'Tab') {
                        e.preventDefault();
                        const start = this.selectionStart;
                        const end = this.selectionEnd;
                        const value = this.value;
                        
                        if (e.shiftKey) {
                            const beforeSelection = value.substring(0, start);
                            const firstLineStart = beforeSelection.lastIndexOf('\\n') + 1;
                            const textBeforeFirstLine = value.substring(0, firstLineStart);
                            const selectedWithFirstLine = value.substring(firstLineStart, end);
                            const unindentedText = selectedWithFirstLine.replace(/^(    |\\t)/gm, '');
                            const removedChars = selectedWithFirstLine.length - unindentedText.length;
                            
                            this.value = textBeforeFirstLine + unindentedText + value.substring(end);
                            this.selectionStart = Math.max(firstLineStart, start - Math.min(4, removedChars));
                            this.selectionEnd = Math.max(this.selectionStart, end - removedChars);
                        } else {
                            if (start === end) {
                                this.value = value.substring(0, start) + '    ' + value.substring(end);
                                this.selectionStart = this.selectionEnd = start + 4;
                            } else {
                                const beforeSelection = value.substring(0, start);
                                const firstLineStart = beforeSelection.lastIndexOf('\\n') + 1;
                                const textBeforeFirstLine = value.substring(0, firstLineStart);
                                const selectedWithFirstLine = value.substring(firstLineStart, end);
                                const indentedText = selectedWithFirstLine.replace(/^/gm, '    ');
                                const addedChars = indentedText.length - selectedWithFirstLine.length;
                                
                                this.value = textBeforeFirstLine + indentedText + value.substring(end);
                                this.selectionStart = start + 4;
                                this.selectionEnd = end + addedChars;
                            }
                        }
                        this.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                });
                return true;
            }
            return false;
        }
        
        let attempts = 0;
        function tryEnable() {
            if (enableTabs()) return;
            attempts++;
            if (attempts < 20) setTimeout(tryEnable, 200);
        }
        tryEnable();
        </script>
        """, height=0)
    
    with col2:
        task = st.selectbox("Analysis Type", ["Explain", "Optimize", "Detect Issues", "Test"])
        
        task_descriptions = {
            "Explain": "Get a detailed step-by-step explanation",
            "Optimize": "Improve performance and efficiency", 
            "Detect Issues": "Find problems and bad practices",
            "Test": "Generate test data and expected results"
        }
        
        st.info(task_descriptions[task])
        
        if st.button("Format SQL", use_container_width=True):
            if sql_query.strip():
                formatted_sql = format_sql(sql_query)
                st.session_state.formatted_sql = formatted_sql
                st.session_state.current_sql_query = formatted_sql
                st.rerun()
            else:
                st.warning("Please enter SQL code to format")
        
        analyze_button = st.button("Analyze Query", use_container_width=True, type="primary",
                                  disabled=(not st.session_state.is_admin and st.session_state.query_count >= 5))
    
    st.markdown("</div>", unsafe_allow_html=True)
    
    if analyze_button:
        if not sql_query.strip():
            st.error("Please enter a SQL query.")
        elif not st.session_state.is_admin and st.session_state.query_count >= 5:
            st.error("Daily query limit reached. Limit resets in 24 hours.")
        else:
            if not st.session_state.is_admin:
                st.session_state.query_count += 1
            
            model = "gpt-4o-mini"
            temperature = 0.3
            max_tokens = 1500
            client = openai.OpenAI(api_key=OPENAI_API_KEY)
            
            def estimate_tokens(text):
                enc = tiktoken.encoding_for_model(model)
                return len(enc.encode(text))
            
            prompt_templates = {
                "Explain": f"""You are a senior database architect with 15+ years of experience across multiple database systems.

Your task is to provide a comprehensive analysis of the following SQL query for a database professional.

Please structure your response as follows:

1. QUERY PURPOSE
   - What business problem this query solves
   - Expected output and use case

2. EXECUTION BREAKDOWN
   - Step-by-step execution order with explanations
   - How the query engine processes each clause
   - Data flow between operations

3. TECHNICAL ANALYSIS
   - Table relationships and join types
   - Filtering and aggregation logic
   - Potential index usage patterns

4. PERFORMANCE CONSIDERATIONS
   - Query complexity assessment
   - Likely bottlenecks or expensive operations
   - Scalability implications

5. ASSUMPTIONS & DEPENDENCIES
   - Required table structures
   - Data distribution assumptions
   - Missing context that might affect analysis

Provide specific, actionable insights rather than generic explanations. Use technical terminology appropriately.

SQL Query:
{sql_query}""",

                "Detect Issues": f"""You are a senior database performance consultant specializing in SQL code review and optimization.

Analyze the following query and identify issues across these categories:

1. PERFORMANCE ISSUES
   - Inefficient joins or subqueries
   - Missing or misused indexes
   - Unnecessary data processing
   - Scalability concerns

2. SECURITY VULNERABILITIES
   - SQL injection risks
   - Excessive permissions required
   - Data exposure concerns

3. MAINTAINABILITY PROBLEMS
   - Code readability issues
   - Hard-coded values
   - Complex logic that could be simplified
   - Missing documentation needs

4. BEST PRACTICE VIOLATIONS
   - SQL standard deviations
   - Database-specific anti-patterns
   - Naming convention issues
   - Resource management concerns

For each issue identified:
- Rate severity: CRITICAL, HIGH, MEDIUM, LOW
- Explain the potential impact
- Provide specific remediation steps
- Suggest alternative approaches where applicable

If no issues are found, explain why the query follows good practices.

SQL Query:
{sql_query}""",

                "Optimize": f"""You are a database performance specialist with expertise in query optimization across multiple database platforms.

Your task is to optimize the following SQL query for better performance.

Please provide:

1. PERFORMANCE ANALYSIS
   - Current query execution approach
   - Identify performance bottlenecks
   - Estimated relative cost of each operation

2. OPTIMIZATION STRATEGY
   - Primary optimization opportunities
   - Index recommendations (existing and new)
   - Query structure improvements
   - Alternative algorithmic approaches

3. OPTIMIZED VERSION
   - Rewritten query with improvements
   - Explanation of each change made
   - Expected performance impact

4. IMPLEMENTATION NOTES
   - Database-specific considerations
   - Index creation statements if needed
   - Testing recommendations
   - Monitoring suggestions

5. TRADE-OFF ANALYSIS
   - Performance vs readability
   - Memory vs CPU usage
   - Optimization maintenance overhead

Assume a medium-to-large dataset unless obvious otherwise. Focus on scalable solutions.

Original SQL Query:
{sql_query}""",

                "Test": f"""You are a database testing specialist responsible for comprehensive SQL query validation.

Create a complete test suite for the following query:

1. TEST DATA DESIGN
   - Generate 5-8 rows of realistic sample data for each table
   - Include edge cases: nulls, empty strings, boundary values
   - Represent different data scenarios (high/low volumes, various patterns)

2. EXPECTED RESULTS
   - Show the complete expected output for your test data
   - Explain the logic for each result row
   - Highlight any complex calculations or transformations

3. EDGE CASE SCENARIOS
   - Empty table conditions
   - Single row scenarios  
   - Null value handling
   - Data type boundary conditions
   - Large dataset implications

4. VALIDATION CRITERIA
   - Data accuracy checks
   - Performance benchmarks
   - Resource usage expectations
   - Error condition handling

5. TEST EXECUTION PLAN
   - Step-by-step testing approach
   - Required test environment setup
   - Success/failure criteria
   - Regression testing considerations

Format the test data as proper INSERT statements and expected results as formatted tables.

SQL Query to Test:
{sql_query}"""
            }
            
            prompt = prompt_templates[task]
            
            with st.spinner("Analyzing your SQL query..."):
                try:
                    token_estimate = estimate_tokens(prompt)
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=temperature,
                        max_tokens=max_tokens
                    )
                    reply = response.choices[0].message.content
                    
                    log_query(user_email=st.session_state.user_email, task_type=task, 
                             query_length=len(sql_query), tokens_used=token_estimate, success=True)
                    
                    try:
                        history_id = save_query_to_history(user_email=st.session_state.user_email, 
                                                         query_text=sql_query, task_type=task, result_text=reply)
                        st.success(f"Analysis complete! (Saved to history: ID {history_id})")
                    except Exception as history_error:
                        st.error(f"Analysis complete but failed to save to history: {str(history_error)}")
                        history_id = None
                    
                    st.markdown("### Analysis Results")
                    
                    col_save1, col_save2, col_save3 = st.columns([2, 1, 1])
                    with col_save1:
                        st.markdown(f"**Task:** {task}")
                    with col_save2:
                        save_name = st.text_input("Save as:", placeholder="Enter name (optional)", key="save_name")
                    with col_save3:
                        if st.button("Save Query", help="Save this query with a custom name"):
                            if history_id and save_name.strip():
                                if update_query_name(history_id, st.session_state.user_email, save_name.strip()):
                                    st.success(f"Renamed to '{save_name}'!")
                                else:
                                    st.error("Failed to update name")
                            elif save_name.strip():
                                st.info("Query name will be applied on next analysis")
                            else:
                                st.info("Query already saved to history")
                    
                    st.markdown("---")
                    st.markdown(reply)
                    
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.caption(f"Tokens used: {token_estimate}")
                    with col_info2:
                        st.caption(f"Model: {model}")
                    with col_info3:
                        st.download_button("Download Results", reply, file_name=f"sql_analysis_{task.lower()}.txt")
                    
                except Exception as e:
                    log_query(user_email=st.session_state.user_email, task_type=task, 
                             query_length=len(sql_query), success=False, error_message=str(e))
                    st.error(f"Error: {str(e)}")

elif st.session_state.current_page == "History":
    st.markdown("## Query History")
    
    with st.expander("Debug Info"):
        st.write(f"Current user: {st.session_state.user_email}")
        
        cursor.execute('SELECT COUNT(*) FROM query_history WHERE user_email = ?', (st.session_state.user_email,))
        total_queries = cursor.fetchone()[0]
        st.write(f"Total queries in history: {total_queries}")
        
        cursor.execute('SELECT COUNT(*) FROM query_history')
        all_queries = cursor.fetchone()[0] 
        st.write(f"Total queries in database (all users): {all_queries}")
        
        cursor.execute('SELECT id, query_text, task_type, timestamp FROM query_history WHERE user_email = ? ORDER BY timestamp DESC LIMIT 3', 
                       (st.session_state.user_email,))
        recent_entries = cursor.fetchall()
        if recent_entries:
            st.write("Your recent entries:")
            for entry in recent_entries:
                st.write(f"ID: {entry[0]}, Task: {entry[2]}, Time: {entry[3]}")
                st.write(f"Query snippet: {entry[1][:50]}...")
        else:
            st.write("No entries found for your account")
            
        cursor.execute('SELECT user_email, task_type, timestamp FROM query_history ORDER BY timestamp DESC LIMIT 5')
        all_recent = cursor.fetchall()
        if all_recent:
            st.write("Recent entries (all users):")
            for entry in all_recent:
                st.write(f"User: {entry[0]}, Task: {entry[1]}, Time: {entry[2]}")
    
    history = get_user_query_history(st.session_state.user_email)
    favorites = get_user_favorites(st.session_state.user_email)
    
    tab1, tab2 = st.tabs(["Recent Queries", "Favorites"])
    
    with tab1:
        st.markdown("### Your Recent Queries")
        
        if history:
            col_search1, col_search2 = st.columns([2, 1])
            with col_search1:
                search_term = st.text_input("Search queries:", placeholder="Search by SQL content or name...")
            with col_search2:
                task_filter = st.selectbox("Filter by task:", ["All", "Explain", "Optimize", "Detect Issues", "Test"])
            
            filtered_history = []
            for item in history:
                query_id, query_text, task_type, result_text, is_favorite, query_name, timestamp = item
                
                if task_filter != "All" and task_type != task_filter:
                    continue
                
                if search_term:
                    search_lower = search_term.lower()
                    if (search_lower not in query_text.lower() and 
                        (not query_name or search_lower not in query_name.lower())):
                        continue
                
                filtered_history.append(item)
            
            if filtered_history:
                st.caption(f"Showing {len(filtered_history)} of {len(history)} queries")
                
                for item in filtered_history:
                    query_id, query_text, task_type, result_text, is_favorite, query_name, timestamp = item
                    
                    display_name = query_name if query_name else f"{task_type} - {timestamp[:10]}"
                    with st.expander(f"{'⭐ ' if is_favorite else ''}{display_name}", expanded=False):
                        
                        col_details1, col_details2, col_details3 = st.columns([2, 1, 1])
                        with col_details1:
                            st.markdown(f"**Task:** {task_type}")
                            st.markdown(f"**Date:** {timestamp}")
                        with col_details2:
                            st.markdown(f"**Length:** {len(query_text)} chars")
                            if query_name:
                                st.markdown(f"**Name:** {query_name}")
                        with col_details3:
                            col_btn1, col_btn2, col_btn3 = st.columns(3)
                            with col_btn1:
                                if st.button("Use", key=f"use_{query_id}", help="Load this query in optimizer"):
                                    st.session_state.selected_history_query = query_text
                                    st.session_state.current_page = "Optimizer"
                                    st.rerun()
                            with col_btn2:
                                fav_label = "Unfav" if is_favorite else "Fav"
                                if st.button(fav_label, key=f"fav_{query_id}", help="Toggle favorite"):
                                    toggle_favorite(query_id)
                                    st.rerun()
                            with col_btn3:
                                if st.button("Delete", key=f"del_{query_id}", help="Delete from history", type="secondary"):
                                    if delete_query_from_history(query_id, st.session_state.user_email):
                                        st.success("Query deleted!")
                                        st.rerun()
                        
                        st.markdown("**SQL Query:**")
                        st.code(query_text, language="sql")
                        
                        if result_text:
                            with st.expander("View Analysis Result"):
                                st.markdown(result_text)
            else:
                if search_term or task_filter != "All":
                    st.info("No queries match your search criteria.")
                else:
                    st.info("No queries found.")
        else:
            st.info("No query history yet. Start by analyzing some SQL queries!")
    
    with tab2:
        st.markdown("### Your Favorite Queries")
        
        if favorites:
            st.caption(f"{len(favorites)} favorite queries")
            
            for item in favorites:
                query_id, query_text, task_type, result_text, query_name, timestamp = item
                
                display_name = query_name if query_name else f"{task_type} - {timestamp[:10]}"
                with st.expander(f"⭐ {display_name}", expanded=False):
                    
                    col_fav1, col_fav2 = st.columns([3, 1])
                    with col_fav1:
                        st.markdown(f"**Task:** {task_type} | **Date:** {timestamp}")
                        if query_name:
                            st.markdown(f"**Name:** {query_name}")
                    with col_fav2:
                        col_fav_btn1, col_fav_btn2 = st.columns(2)
                        with col_fav_btn1:
                            if st.button("Use", key=f"use_fav_{query_id}"):
                                st.session_state.selected_history_query = query_text
                                st.session_state.current_page = "Optimizer"
                                st.rerun()
                        with col_fav_btn2:
                            if st.button("Unfav", key=f"unfav_{query_id}", type="secondary"):
                                toggle_favorite(query_id)
                                st.rerun()
                    
                    col_rename1, col_rename2 = st.columns([2, 1])
                    with col_rename1:
                        new_name = st.text_input("Rename:", value=query_name or "", key=f"rename_{query_id}")
                    with col_rename2:
                        if st.button("Update Name", key=f"update_{query_id}"):
                            if update_query_name(query_id, st.session_state.user_email, new_name.strip()):
                                st.success("Name updated!")
                                st.rerun()
                    
                    st.markdown("**SQL Query:**")
                    st.code(query_text, language="sql")
                    
                    if result_text:
                        with st.expander("View Analysis Result"):
                            st.markdown(result_text)
        else:
            st.info("No favorite queries yet. Star some queries from your history to see them here!")

elif st.session_state.current_page == "Analytics" and st.session_state.is_admin:
    st.markdown("## Analytics Dashboard")
    
    col_refresh1, col_refresh2, col_refresh3, col_refresh4 = st.columns([1, 1, 1, 2])
    
    with col_refresh1:
        manual_refresh = st.button("Refresh", use_container_width=True)
    
    with col_refresh2:
        auto_refresh = st.toggle("Auto-refresh")
    
    with col_refresh3:
        refresh_rate = st.selectbox("Rate (s)", [15, 30, 60], index=1)
    
    analytics_data, is_fresh = get_analytics_data_cached(force_refresh=manual_refresh)
    
    with col_refresh4:
        if st.session_state.last_analytics_update:
            last_update = st.session_state.last_analytics_update
            age_seconds = (datetime.now() - last_update).total_seconds()
            
            if is_fresh:
                st.success(f"Just updated!")
            elif age_seconds < 60:
                st.info(f"Updated {int(age_seconds)}s ago")
            else:
                st.warning(f"Updated {int(age_seconds/60)}m ago")
    
    if auto_refresh:
        if st.session_state.last_analytics_update:
            age = (datetime.now() - st.session_state.last_analytics_update).total_seconds()
            if age >= refresh_rate:
                st.rerun()
    
    st.markdown("### Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="Total Users", value=analytics_data['total_users'], 
                 delta=f"{analytics_data['active_users_7d']} active (7d)")
    
    with col2:
        st.metric(label="Total Queries", value=analytics_data['total_queries'],
                 delta=f"{analytics_data['success_rate']:.1f}% success rate")
    
    with col3:
        estimated_cost = (analytics_data['total_tokens'] / 1000) * 0.000150
        st.metric(label="API Costs", value=f"${estimated_cost:.3f}",
                 delta=f"{analytics_data['total_tokens']:,} tokens")
    
    with col4:
        popular_task = analytics_data['queries_by_task'][0][0] if analytics_data['queries_by_task'] else "None"
        st.metric(label="Most Popular Task", value=popular_task,
                 delta=f"Avg {analytics_data['avg_query_length']} chars/query")
    
    tab1, tab2, tab3, tab4 = st.tabs(["Usage Trends", "User Activity", "Task Types", "Errors"])
    
    with tab1:
        st.markdown("#### Query Activity")
        cursor.execute('''SELECT user_email, task_type, timestamp FROM query_logs 
                         WHERE timestamp >= datetime('now', '-2 hours') ORDER BY timestamp DESC LIMIT 8''')
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
                
                st.markdown(f"**{email}** used *{task}* {time_str}")
        else:
            st.info("No recent activity")
    
    with tab2:
        cursor.execute('''SELECT ql.user_email, u.name, COUNT(*) as query_count 
                         FROM query_logs ql LEFT JOIN users u ON ql.user_email = u.email 
                         GROUP BY ql.user_email ORDER BY query_count DESC LIMIT 10''')
        top_users = cursor.fetchall()
        
        if top_users:
            df_users = pd.DataFrame(top_users, columns=['Email', 'Name', 'Query Count'])
            st.dataframe(df_users, use_container_width=True)
        else:
            st.info("No user data available yet")
    
    with tab3:
        if analytics_data['queries_by_task']:
            col_task1, col_task2 = st.columns([1, 1])
            
            with col_task1:
                df_tasks = pd.DataFrame(analytics_data['queries_by_task'], columns=['Task Type', 'Count'])
                st.bar_chart(df_tasks.set_index('Task Type'), use_container_width=True)
            
            with col_task2:
                st.dataframe(df_tasks, use_container_width=True)
        else:
            st.info("No task data available yet")
    
    with tab4:
        cursor.execute('''SELECT user_email, task_type, error_message, timestamp FROM query_logs 
                         WHERE success = 0 ORDER BY timestamp DESC LIMIT 10''')
        recent_errors = cursor.fetchall()
        
        if recent_errors:
            df_errors = pd.DataFrame(recent_errors, columns=['User Email', 'Task Type', 'Error', 'Timestamp'])
            st.dataframe(df_errors, use_container_width=True)
        else:
            st.success("No recent errors!")

elif st.session_state.current_page == "Users" and st.session_state.is_admin:
    st.markdown("## User Management")
    
    tab1, tab2, tab3 = st.tabs(["All Users", "Manage Users", "User Analytics"])
    
    with tab1:
        st.markdown("#### All Registered Users")
        cursor.execute('SELECT email, name, admin FROM users')
        users = cursor.fetchall()
        
        if users:
            df = pd.DataFrame(users, columns=['Email', 'Name', 'Admin Status'])
            df['Admin Status'] = df['Admin Status'].map({1: 'Admin', 0: 'User', None: 'User'})
            st.dataframe(df, use_container_width=True)
            st.caption(f"Total users: {len(users)}")
        else:
            st.info("No users found")
    
    with tab2:
        col_manage1, col_manage2 = st.columns(2)
        
        with col_manage1:
            st.markdown("#### Grant Admin Access")
            cursor.execute('SELECT email, name FROM users WHERE admin = 0 OR admin IS NULL')
            regular_users = cursor.fetchall()
            
            if regular_users:
                user_options = [f"{user[1]} ({user[0]})" for user in regular_users]
                selected_user_idx = st.selectbox("Select user:", range(len(user_options)), 
                                                format_func=lambda x: user_options[x])
                selected_email = regular_users[selected_user_idx][0]
                
                if st.button("Grant Admin Access", use_container_width=True, type="primary"):
                    cursor.execute('UPDATE users SET admin = 1 WHERE email = ?', (selected_email,))
                    conn.commit()
                    st.success(f"{selected_email} is now an admin!")
                    st.rerun()
            else:
                st.info("All users are already admins")
        
        with col_manage2:
            st.markdown("#### Remove User")
            cursor.execute('SELECT email, name FROM users')
            all_users = cursor.fetchall()
            
            if len(all_users) > 1:
                user_options_delete = [f"{user[1]} ({user[0]})" for user in all_users]
                selected_user_delete_idx = st.selectbox("Select user to delete:", range(len(user_options_delete)), 
                                                       format_func=lambda x: user_options_delete[x], key="delete_user")
                selected_email_delete = all_users[selected_user_delete_idx][0]
                
                if selected_email_delete != st.session_state.user_email:
                    if st.button("Delete User", use_container_width=True, type="secondary"):
                        cursor.execute('DELETE FROM users WHERE email = ?', (selected_email_delete,))
                        conn.commit()
                        st.success(f"User {selected_email_delete} deleted!")
                        st.rerun()
                else:
                    st.error("Cannot delete your own account!")
            else:
                st.info("Cannot delete users - you're the only one!")
    
    with tab3:
        st.markdown("#### Individual User Statistics")
        
        cursor.execute('''SELECT u.email, u.name, COUNT(ql.id) as total_queries,
                         SUM(CASE WHEN ql.success = 1 THEN 1 ELSE 0 END) as successful_queries,
                         MAX(ql.timestamp) as last_activity
                         FROM users u LEFT JOIN query_logs ql ON u.email = ql.user_email
                         GROUP BY u.email, u.name ORDER BY total_queries DESC''')
        
        user_stats = cursor.fetchall()
        
        if user_stats:
            for stat in user_stats:
                email, name, total, success, last_activity = stat
                success_rate = (success / total * 100) if total > 0 else 0
                
                with st.expander(f"{name} ({email})"):
                    col_stat1, col_stat2, col_stat3 = st.columns(3)
                    
                    with col_stat1:
                        st.metric("Total Queries", total or 0)
                    with col_stat2:
                        st.metric("Success Rate", f"{success_rate:.1f}%" if total > 0 else "N/A")
                    with col_stat3:
                        st.metric("Last Activity", last_activity or "Never")
                    
                    if total > 0:
                        cursor.execute('SELECT task_type, COUNT(*) as count FROM query_logs WHERE user_email = ? GROUP BY task_type', 
                                     (email,))
                        user_tasks = cursor.fetchall()
                        if user_tasks:
                            st.markdown("**Task Breakdown:**")
                            for task, count in user_tasks:
                                st.markdown(f"- {task}: {count} queries")
        else:
            st.info("No user activity data available")

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem 0;">
    <p>SQL Optimizer AI - Powered by GPT-4o Mini</p>
    <p>Built with Streamlit</p>
</div>
""", unsafe_allow_html=True)