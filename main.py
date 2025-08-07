import streamlit as st
import streamlit.components.v1
import openai
import tiktoken
from datetime import datetime, timedelta
import bcrypt
import pandas as pd
from supabase import create_client, Client
import uuid

# === Load from Streamlit Secrets (for Streamlit Cloud) ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# === Initialize Supabase Client ===
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

# === Page Configuration ===
st.set_page_config(
    page_title="SQL Optimizer",
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
</style>
""", unsafe_allow_html=True)

# === Database Functions ===
def create_tables():
    """Create tables in Supabase if they don't exist"""
    # Note: These tables should be created in Supabase Dashboard
    # This is just for reference of the schema
    """
    CREATE TABLE IF NOT EXISTS users (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        email TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        password TEXT NOT NULL,
        admin BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS query_logs (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_email TEXT NOT NULL,
        task_type TEXT NOT NULL,
        query_length INTEGER NOT NULL,
        tokens_used INTEGER,
        success BOOLEAN NOT NULL,
        error_message TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    
    CREATE TABLE IF NOT EXISTS query_history (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_email TEXT NOT NULL,
        query_text TEXT NOT NULL,
        task_type TEXT NOT NULL,
        result_text TEXT,
        is_favorite BOOLEAN DEFAULT FALSE,
        query_name TEXT,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );
    """
    pass

# === User Functions ===
def add_user(email, name, password, is_admin=False):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        data = {
            "email": email,
            "name": name,
            "password": hashed_password,
            "admin": is_admin
        }
        result = supabase.table('users').insert(data).execute()
        return True
    except Exception as e:
        st.error(f"Error creating user: {str(e)}")
        return False

def get_user(email):
    try:
        result = supabase.table('users').select("*").eq('email', email).execute()
        if result.data:
            return result.data[0]
        return None
    except Exception as e:
        st.error(f"Error fetching user: {str(e)}")
        return None

def verify_password(stored_password, provided_password):
    return bcrypt.checkpw(provided_password.encode(), stored_password.encode())

def log_query(user_email, task_type, query_length, tokens_used=None, success=True, error_message=None):
    try:
        data = {
            "user_email": user_email,
            "task_type": task_type,
            "query_length": query_length,
            "tokens_used": tokens_used,
            "success": success,
            "error_message": error_message
        }
        supabase.table('query_logs').insert(data).execute()
    except Exception as e:
        st.error(f"Error logging query: {str(e)}")

def save_query_to_history(user_email, query_text, task_type, result_text=None, query_name=None):
    try:
        data = {
            "user_email": user_email,
            "query_text": query_text,
            "task_type": task_type,
            "result_text": result_text,
            "query_name": query_name
        }
        result = supabase.table('query_history').insert(data).execute()
        if result.data:
            return result.data[0]['id']
        return None
    except Exception as e:
        st.error(f"Error saving to history: {str(e)}")
        return None

def get_user_query_history(user_email, limit=50):
    try:
        result = supabase.table('query_history').select("*").eq('user_email', user_email).order('created_at', desc=True).limit(limit).execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error fetching history: {str(e)}")
        return []

def get_user_favorites(user_email):
    try:
        result = supabase.table('query_history').select("*").eq('user_email', user_email).eq('is_favorite', True).order('created_at', desc=True).execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error fetching favorites: {str(e)}")
        return []

def toggle_favorite(query_id):
    try:
        # First get current status
        result = supabase.table('query_history').select("is_favorite").eq('id', query_id).execute()
        if result.data:
            current_status = result.data[0]['is_favorite']
            new_status = not current_status
            supabase.table('query_history').update({"is_favorite": new_status}).eq('id', query_id).execute()
            return new_status
    except Exception as e:
        st.error(f"Error toggling favorite: {str(e)}")
        return False

def delete_query_from_history(query_id, user_email):
    try:
        result = supabase.table('query_history').delete().eq('id', query_id).eq('user_email', user_email).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting query: {str(e)}")
        return False

def update_query_name(query_id, user_email, new_name):
    try:
        supabase.table('query_history').update({"query_name": new_name}).eq('id', query_id).eq('user_email', user_email).execute()
        return True
    except Exception as e:
        st.error(f"Error updating query name: {str(e)}")
        return False

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
    try:
        # Total queries
        result = supabase.table('query_logs').select("*", count='exact').execute()
        analytics['total_queries'] = result.count if result.count else 0
        
        # Success rate
        success_result = supabase.table('query_logs').select("*", count='exact').eq('success', True).execute()
        successful_queries = success_result.count if success_result.count else 0
        analytics['success_rate'] = (successful_queries / analytics['total_queries'] * 100) if analytics['total_queries'] > 0 else 0
        
        # Queries by task type
        task_result = supabase.table('query_logs').select("task_type").execute()
        if task_result.data:
            task_counts = {}
            for row in task_result.data:
                task = row['task_type']
                task_counts[task] = task_counts.get(task, 0) + 1
            analytics['queries_by_task'] = sorted(task_counts.items(), key=lambda x: x[1], reverse=True)
        else:
            analytics['queries_by_task'] = []
        
        # Total users
        users_result = supabase.table('users').select("*", count='exact').execute()
        analytics['total_users'] = users_result.count if users_result.count else 0
        
        # Active users in last 7 days
        seven_days_ago = (datetime.now() - timedelta(days=7)).isoformat()
        active_result = supabase.table('query_logs').select("user_email").gte('created_at', seven_days_ago).execute()
        if active_result.data:
            unique_users = set(row['user_email'] for row in active_result.data)
            analytics['active_users_7d'] = len(unique_users)
        else:
            analytics['active_users_7d'] = 0
        
        # Average query length
        length_result = supabase.table('query_logs').select("query_length").execute()
        if length_result.data:
            lengths = [row['query_length'] for row in length_result.data]
            analytics['avg_query_length'] = round(sum(lengths) / len(lengths), 0) if lengths else 0
        else:
            analytics['avg_query_length'] = 0
        
        # Total tokens
        tokens_result = supabase.table('query_logs').select("tokens_used").execute()
        if tokens_result.data:
            tokens = [row['tokens_used'] for row in tokens_result.data if row['tokens_used']]
            analytics['total_tokens'] = sum(tokens) if tokens else 0
        else:
            analytics['total_tokens'] = 0
            
    except Exception as e:
        st.error(f"Error fetching analytics: {str(e)}")
        analytics = {
            'total_queries': 0,
            'success_rate': 0,
            'queries_by_task': [],
            'total_users': 0,
            'active_users_7d': 0,
            'avg_query_length': 0,
            'total_tokens': 0
        }
    
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
    <h1>SQL Optimizer</h1>
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
                if not user:
                    st.error("User not found. Please check your email or register.")
                else:
                    stored_password = user['password']
                    
                    if verify_password(stored_password, password):
                        st.session_state.logged_in = True
                        st.session_state.user_email = email
                        st.session_state.is_admin = user.get('admin', False) or (email in ADMIN_EMAILS)
                        st.rerun()
                    else:
                        st.error("Invalid password")

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
                    is_admin = new_email in ADMIN_EMAILS
                    if add_user(new_email, new_name, new_password, is_admin):
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
        try:
            result = supabase.table('query_logs').select("task_type, created_at").eq('user_email', st.session_state.user_email).order('created_at', desc=True).limit(5).execute()
            recent_activity = result.data if result.data else []
            
            if recent_activity:
                for activity in recent_activity:
                    task = activity['task_type']
                    timestamp = activity['created_at']
                    st.markdown(f"- **{task}** query on {timestamp}")
            else:
                st.info("No recent activity. Start by analyzing your first SQL query!")
        except Exception as e:
            st.info("No recent activity. Start by analyzing your first SQL query!")
    
    with col2:
        st.markdown("## Your Stats")
        
        try:
            # Total queries
            total_result = supabase.table('query_logs').select("*", count='exact').eq('user_email', st.session_state.user_email).execute()
            user_queries = total_result.count if total_result.count else 0
            
            # Success rate
            success_result = supabase.table('query_logs').select("*", count='exact').eq('user_email', st.session_state.user_email).eq('success', True).execute()
            user_success = success_result.count if success_result.count else 0
            
            success_rate = (user_success / user_queries * 100) if user_queries > 0 else 0
            
            st.metric("Total Queries", user_queries)
            st.metric("Success Rate", f"{success_rate:.1f}%")
            
            if not st.session_state.is_admin:
                st.metric("Daily Remaining", 5 - st.session_state.query_count)
        except Exception as e:
            st.metric("Total Queries", 0)
            st.metric("Success Rate", "0.0%")
            if not st.session_state.is_admin:
                st.metric("Daily Remaining", 5 - st.session_state.query_count)

elif st.session_state.current_page == "Optimizer":
    st.markdown("## SQL Query Optimizer")
    
    #st.markdown('<div class="query-container">', unsafe_allow_html=True)
    
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
    
    with col2:
        task = st.selectbox("Analysis Type", ["Explain", "Optimize", "Detect Issues", "Test"])
        
        task_descriptions = {
            "Explain": "Get a detailed step-by-step explanation",
            "Optimize": "Improve performance and efficiency", 
            "Detect Issues": "Find problems and bad practices",
            "Test": "Generate test data and expected results"
        }
        
        st.info(task_descriptions[task])
        
        analyze_button = st.button("Analyze Query", use_container_width=True, type="primary",
                                  disabled=(not st.session_state.is_admin and st.session_state.query_count >= 5))
        
        if st.button("Format SQL", use_container_width=True):
            if sql_query.strip():
                formatted_sql = format_sql(sql_query)
                st.session_state.formatted_sql = formatted_sql
                st.session_state.current_sql_query = formatted_sql
                st.rerun()
            else:
                st.warning("Please enter SQL code to format")
        
        
    
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
                "Explain": f"""Provide a comprehensive analysis of this SQL query.

Structure your response:
1. QUERY PURPOSE - What problem it solves
2. EXECUTION BREAKDOWN - Step-by-step processing
3. TECHNICAL ANALYSIS - Table relationships and logic
4. PERFORMANCE CONSIDERATIONS - Bottlenecks and scalability
5. ASSUMPTIONS & DEPENDENCIES

SQL Query:
{sql_query}""",

                "Detect Issues": f"""Analyze this query for issues.

Check for:
1. PERFORMANCE ISSUES - Inefficiencies
2. SECURITY VULNERABILITIES - Injection risks
3. MAINTAINABILITY PROBLEMS - Readability issues
4. BEST PRACTICE VIOLATIONS

Rate severity: CRITICAL, HIGH, MEDIUM, LOW

SQL Query:
{sql_query}""",

                "Optimize": f"""Optimize this SQL query for better performance.

Provide:
1. PERFORMANCE ANALYSIS
2. OPTIMIZATION STRATEGY
3. OPTIMIZED VERSION
4. IMPLEMENTATION NOTES
5. TRADE-OFF ANALYSIS

Original SQL Query:
{sql_query}""",

                "Test": f"""Create a test suite for this query.

Include:
1. TEST DATA DESIGN - Sample data with edge cases
2. EXPECTED RESULTS - Complete output
3. EDGE CASE SCENARIOS
4. VALIDATION CRITERIA
5. TEST EXECUTION PLAN

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
                if task_filter != "All" and item['task_type'] != task_filter:
                    continue
                
                if search_term:
                    search_lower = search_term.lower()
                    if (search_lower not in item['query_text'].lower() and 
                        (not item.get('query_name') or search_lower not in item['query_name'].lower())):
                        continue
                
                filtered_history.append(item)
            
            if filtered_history:
                st.caption(f"Showing {len(filtered_history)} of {len(history)} queries")
                
                for item in filtered_history:
                    star_mark = "[Favorite] " if item.get('is_favorite') else ""
                    display_name = item.get('query_name') if item.get('query_name') else f"{item['task_type']} - {item['created_at'][:10]}"
                    with st.expander(f"{star_mark}{display_name}", expanded=False):
                        
                        col_details1, col_details2, col_details3 = st.columns([2, 1, 1])
                        with col_details1:
                            st.markdown(f"**Task:** {item['task_type']}")
                            st.markdown(f"**Date:** {item['created_at']}")
                        with col_details2:
                            st.markdown(f"**Length:** {len(item['query_text'])} chars")
                            if item.get('query_name'):
                                st.markdown(f"**Name:** {item['query_name']}")
                        with col_details3:
                            col_btn1, col_btn2, col_btn3 = st.columns(3)
                            with col_btn1:
                                if st.button("Use", key=f"use_{item['id']}", help="Load this query in optimizer"):
                                    st.session_state.selected_history_query = item['query_text']
                                    st.session_state.current_page = "Optimizer"
                                    st.rerun()
                            with col_btn2:
                                fav_label = "Unfav" if item.get('is_favorite') else "Fav"
                                if st.button(fav_label, key=f"fav_{item['id']}", help="Toggle favorite"):
                                    toggle_favorite(item['id'])
                                    st.rerun()
                            with col_btn3:
                                if st.button("Delete", key=f"del_{item['id']}", help="Delete from history", type="secondary"):
                                    if delete_query_from_history(item['id'], st.session_state.user_email):
                                        st.success("Query deleted!")
                                        st.rerun()
                        
                        st.markdown("**SQL Query:**")
                        st.code(item['query_text'], language="sql")
                        
                        if item.get('result_text'):
                            with st.expander("View Analysis Result"):
                                st.markdown(item['result_text'])
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
                display_name = item.get('query_name') if item.get('query_name') else f"{item['task_type']} - {item['created_at'][:10]}"
                with st.expander(f"[Favorite] {display_name}", expanded=False):
                    
                    col_fav1, col_fav2 = st.columns([3, 1])
                    with col_fav1:
                        st.markdown(f"**Task:** {item['task_type']} | **Date:** {item['created_at']}")
                        if item.get('query_name'):
                            st.markdown(f"**Name:** {item['query_name']}")
                    with col_fav2:
                        col_fav_btn1, col_fav_btn2 = st.columns(2)
                        with col_fav_btn1:
                            if st.button("Use", key=f"use_fav_{item['id']}"):
                                st.session_state.selected_history_query = item['query_text']
                                st.session_state.current_page = "Optimizer"
                                st.rerun()
                        with col_fav_btn2:
                            if st.button("Unfav", key=f"unfav_{item['id']}", type="secondary"):
                                toggle_favorite(item['id'])
                                st.rerun()
                    
                    col_rename1, col_rename2 = st.columns([2, 1])
                    with col_rename1:
                        new_name = st.text_input("Rename:", value=item.get('query_name', ''), key=f"rename_{item['id']}")
                    with col_rename2:
                        if st.button("Update Name", key=f"update_{item['id']}"):
                            if update_query_name(item['id'], st.session_state.user_email, new_name.strip()):
                                st.success("Name updated!")
                                st.rerun()
                    
                    st.markdown("**SQL Query:**")
                    st.code(item['query_text'], language="sql")
                    
                    if item.get('result_text'):
                        with st.expander("View Analysis Result"):
                            st.markdown(item['result_text'])
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
        try:
            two_hours_ago = (datetime.now() - timedelta(hours=2)).isoformat()
            result = supabase.table('query_logs').select("user_email, task_type, created_at").gte('created_at', two_hours_ago).order('created_at', desc=True).limit(8).execute()
            recent_queries = result.data if result.data else []
            
            if recent_queries:
                for query in recent_queries:
                    email = query['user_email']
                    task = query['task_type']
                    timestamp = query['created_at']
                    query_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00').replace('+00:00', ''))
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
        except Exception as e:
            st.info("No recent activity")
    
    with tab2:
        try:
            # Get user query counts
            logs_result = supabase.table('query_logs').select("user_email").execute()
            users_result = supabase.table('users').select("email, name").execute()
            
            if logs_result.data and users_result.data:
                user_counts = {}
                user_names = {u['email']: u['name'] for u in users_result.data}
                
                for log in logs_result.data:
                    email = log['user_email']
                    user_counts[email] = user_counts.get(email, 0) + 1
                
                top_users = sorted(user_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                top_users_data = [[email, user_names.get(email, 'Unknown'), count] for email, count in top_users]
                
                df_users = pd.DataFrame(top_users_data, columns=['Email', 'Name', 'Query Count'])
                st.dataframe(df_users, use_container_width=True)
            else:
                st.info("No user data available yet")
        except Exception as e:
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
        try:
            result = supabase.table('query_logs').select("user_email, task_type, error_message, created_at").eq('success', False).order('created_at', desc=True).limit(10).execute()
            recent_errors = result.data if result.data else []
            
            if recent_errors:
                df_errors = pd.DataFrame(recent_errors, columns=['user_email', 'task_type', 'error_message', 'created_at'])
                df_errors.columns = ['User Email', 'Task Type', 'Error', 'Timestamp']
                st.dataframe(df_errors, use_container_width=True)
            else:
                st.success("No recent errors!")
        except Exception as e:
            st.success("No recent errors!")

elif st.session_state.current_page == "Users" and st.session_state.is_admin:
    st.markdown("## User Management")
    
    tab1, tab2, tab3 = st.tabs(["All Users", "Manage Users", "User Analytics"])
    
    with tab1:
        st.markdown("#### All Registered Users")
        try:
            result = supabase.table('users').select("email, name, admin").execute()
            users = result.data if result.data else []
            
            if users:
                df = pd.DataFrame(users)
                df['admin'] = df['admin'].map({True: 'Admin', False: 'User', None: 'User'})
                df.columns = ['Email', 'Name', 'Admin Status']
                st.dataframe(df, use_container_width=True)
                st.caption(f"Total users: {len(users)}")
            else:
                st.info("No users found")
        except Exception as e:
            st.info("No users found")
    
    with tab2:
        col_manage1, col_manage2 = st.columns(2)
        
        with col_manage1:
            st.markdown("#### Grant Admin Access")
            try:
                result = supabase.table('users').select("email, name").eq('admin', False).execute()
                regular_users = result.data if result.data else []
                
                if regular_users:
                    user_options = [f"{user['name']} ({user['email']})" for user in regular_users]
                    selected_user_idx = st.selectbox("Select user:", range(len(user_options)), 
                                                    format_func=lambda x: user_options[x])
                    selected_email = regular_users[selected_user_idx]['email']
                    
                    if st.button("Grant Admin Access", use_container_width=True, type="primary"):
                        supabase.table('users').update({"admin": True}).eq('email', selected_email).execute()
                        st.success(f"{selected_email} is now an admin!")
                        st.rerun()
                else:
                    st.info("All users are already admins")
            except Exception as e:
                st.error(f"Error: {str(e)}")
            
            # Password Reset Tool
            st.markdown("#### Reset User Password")
            try:
                result = supabase.table('users').select("email, name").execute()
                all_users_reset = result.data if result.data else []
                
                if all_users_reset:
                    user_options_reset = [f"{user['name']} ({user['email']})" for user in all_users_reset]
                    selected_user_reset_idx = st.selectbox("Select user to reset password:", range(len(user_options_reset)), 
                                                          format_func=lambda x: user_options_reset[x], key="reset_user")
                    selected_email_reset = all_users_reset[selected_user_reset_idx]['email']
                    
                    new_password = st.text_input("New password:", type="password", key="new_password")
                    
                    if st.button("Reset Password", use_container_width=True, type="secondary"):
                        if new_password.strip():
                            # Hash the new password
                            hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
                            supabase.table('users').update({"password": hashed_password}).eq('email', selected_email_reset).execute()
                            st.success(f"Password reset for {selected_email_reset}!")
                        else:
                            st.error("Please enter a new password")
            except Exception as e:
                st.error(f"Error: {str(e)}")
        
        with col_manage2:
            st.markdown("#### Remove User")
            try:
                result = supabase.table('users').select("email, name").execute()
                all_users = result.data if result.data else []
                
                if len(all_users) > 1:
                    user_options_delete = [f"{user['name']} ({user['email']})" for user in all_users]
                    selected_user_delete_idx = st.selectbox("Select user to delete:", range(len(user_options_delete)), 
                                                           format_func=lambda x: user_options_delete[x], key="delete_user")
                    selected_email_delete = all_users[selected_user_delete_idx]['email']
                    
                    if selected_email_delete != st.session_state.user_email:
                        if st.button("Delete User", use_container_width=True, type="secondary"):
                            supabase.table('users').delete().eq('email', selected_email_delete).execute()
                            st.success(f"User {selected_email_delete} deleted!")
                            st.rerun()
                    else:
                        st.error("Cannot delete your own account!")
                else:
                    st.info("Cannot delete users - you're the only one!")
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    with tab3:
        st.markdown("#### Individual User Statistics")
        
        try:
            users_result = supabase.table('users').select("email, name").execute()
            logs_result = supabase.table('query_logs').select("user_email, success, created_at").execute()
            
            if users_result.data:
                user_stats = []
                for user in users_result.data:
                    email = user['email']
                    name = user['name']
                    
                    # Calculate stats for this user
                    user_logs = [log for log in (logs_result.data or []) if log['user_email'] == email]
                    total = len(user_logs)
                    success = len([log for log in user_logs if log['success']])
                    last_activity = max([log['created_at'] for log in user_logs]) if user_logs else None
                    
                    user_stats.append((email, name, total, success, last_activity))
                
                # Sort by total queries
                user_stats.sort(key=lambda x: x[2], reverse=True)
                
                for email, name, total, success, last_activity in user_stats:
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
                            # Get task breakdown
                            task_counts = {}
                            for log in user_logs:
                                task = log.get('task_type', 'Unknown')
                                task_counts[task] = task_counts.get(task, 0) + 1
                            
                            st.markdown("**Task Breakdown:**")
                            for task, count in task_counts.items():
                                st.markdown(f"- {task}: {count} queries")
            else:
                st.info("No user activity data available")
        except Exception as e:
            st.info("No user activity data available")

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem 0;">
</div>
""", unsafe_allow_html=True)