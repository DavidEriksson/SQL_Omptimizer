import streamlit as st
from config import supabase

def home_page():
    """Render the home page"""
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