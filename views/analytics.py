import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_analytics_data_cached
from config import supabase

def analytics_page():
    """Render the analytics dashboard page"""
    st.markdown("## Analytics Dashboard")
    
    # Refresh controls
    col_refresh1, col_refresh2, col_refresh3, col_refresh4 = st.columns([1, 1, 1, 2])
    
    with col_refresh1:
        manual_refresh = st.button("Refresh", use_container_width=True)
    
    with col_refresh2:
        auto_refresh = st.toggle("Auto-refresh")
    
    with col_refresh3:
        refresh_rate = st.selectbox("Rate (s)", [15, 30, 60], index=1)
    
    analytics_data, is_fresh = get_analytics_data_cached(force_refresh=manual_refresh)
    
    with col_refresh4:
        display_refresh_status(is_fresh)
    
    # Auto-refresh logic
    if auto_refresh and st.session_state.last_analytics_update:
        age = (datetime.now() - st.session_state.last_analytics_update).total_seconds()
        if age >= refresh_rate:
            st.rerun()
    
    # Display metrics
    display_key_metrics(analytics_data)
    
    # Display detailed analytics tabs
    display_analytics_tabs(analytics_data)

def display_refresh_status(is_fresh):
    """Display the data refresh status"""
    if st.session_state.last_analytics_update:
        last_update = st.session_state.last_analytics_update
        age_seconds = (datetime.now() - last_update).total_seconds()
        
        if is_fresh:
            st.success(f"Just updated!")
        elif age_seconds < 60:
            st.info(f"Updated {int(age_seconds)}s ago")
        else:
            st.warning(f"Updated {int(age_seconds/60)}m ago")

def display_key_metrics(analytics_data):
    """Display key metrics cards"""
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

def display_analytics_tabs(analytics_data):
    """Display detailed analytics in tabs"""
    tab1, tab2, tab3, tab4 = st.tabs(["Usage Trends", "User Activity", "Task Types", "Errors"])
    
    with tab1:
        display_usage_trends()
    
    with tab2:
        display_user_activity()
    
    with tab3:
        display_task_types(analytics_data)
    
    with tab4:
        display_errors()

def display_usage_trends():
    """Display recent query activity"""
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

def display_user_activity():
    """Display top users by query count"""
    try:
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

def display_task_types(analytics_data):
    """Display query distribution by task type"""
    if analytics_data['queries_by_task']:
        col_task1, col_task2 = st.columns([1, 1])
        
        with col_task1:
            df_tasks = pd.DataFrame(analytics_data['queries_by_task'], columns=['Task Type', 'Count'])
            st.bar_chart(df_tasks.set_index('Task Type'), use_container_width=True)
        
        with col_task2:
            st.dataframe(df_tasks, use_container_width=True)
    else:
        st.info("No task data available yet")

def display_errors():
    """Display recent errors"""
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