import streamlit as st
import pandas as pd
import bcrypt
from database import (
    get_all_users,
    get_regular_users,
    grant_admin_access,
    reset_user_password,
    delete_user
)
from config import supabase

def users_page():
    """Render the user management page"""
    st.markdown("## User Management")
    
    tab1, tab2, tab3 = st.tabs(["All Users", "Manage Users", "User Analytics"])
    
    with tab1:
        display_all_users()
    
    with tab2:
        display_user_management()
    
    with tab3:
        display_user_analytics()

def display_all_users():
    """Display all registered users"""
    st.markdown("#### All Registered Users")
    
    users = get_all_users()
    
    if users:
        df = pd.DataFrame(users)
        df['is_admin'] = df['is_admin'].map({True: 'Admin', False: 'User', None: 'User'})
        df.columns = ['Email', 'Name', 'Admin Status']
        st.dataframe(df, use_container_width=True)
        st.caption(f"Total users: {len(users)}")
    else:
        st.info("No users found")

def display_user_management():
    """Display user management controls"""
    col_manage1, col_manage2 = st.columns(2)
    
    with col_manage1:
        manage_admin_access()
        reset_password_tool()
    
    with col_manage2:
        remove_user_tool()

def manage_admin_access():
    """Grant admin access to users"""
    st.markdown("#### Grant Admin Access")
    
    regular_users = get_regular_users()
    
    if regular_users:
        user_options = [f"{user['name']} ({user['email']})" for user in regular_users]
        selected_user_idx = st.selectbox("Select user:", range(len(user_options)), 
                                        format_func=lambda x: user_options[x])
        selected_email = regular_users[selected_user_idx]['email']
        
        if st.button("Grant Admin Access", use_container_width=True, type="primary"):
            if grant_admin_access(selected_email):
                st.success(f"{selected_email} is now an admin!")
                st.rerun()
    else:
        st.info("All users are already admins")

def reset_password_tool():
    """Reset user passwords"""
    st.markdown("#### Reset User Password")
    
    try:
        result = supabase.table('users').select("email, name").execute()
        all_users = result.data if result.data else []
        
        if all_users:
            user_options = [f"{user['name']} ({user['email']})" for user in all_users]
            selected_user_idx = st.selectbox("Select user to reset password:", 
                                            range(len(user_options)), 
                                            format_func=lambda x: user_options[x], 
                                            key="reset_user")
            selected_email = all_users[selected_user_idx]['email']
            
            new_password = st.text_input("New password:", type="password", key="new_password")
            
            if st.button("Reset Password", use_container_width=True, type="secondary"):
                if new_password.strip():
                    if reset_user_password(selected_email, new_password):
                        st.success(f"Password reset for {selected_email}!")
                else:
                    st.error("Please enter a new password")
    except Exception as e:
        st.error(f"Error: {str(e)}")

def remove_user_tool():
    """Remove users from the system"""
    st.markdown("#### Remove User")
    
    users = get_all_users()
    
    if len(users) > 1:
        user_options = [f"{user['name']} ({user['email']})" for user in users]
        selected_user_idx = st.selectbox("Select user to delete:", 
                                        range(len(user_options)), 
                                        format_func=lambda x: user_options[x], 
                                        key="delete_user")
        selected_email = users[selected_user_idx]['email']
        
        if selected_email != st.session_state.user_email:
            if st.button("Delete User", use_container_width=True, type="secondary"):
                if delete_user(selected_email):
                    st.success(f"User {selected_email} deleted!")
                    st.rerun()
        else:
            st.error("Cannot delete your own account!")
    else:
        st.info("Cannot delete users - you're the only one!")

def display_user_analytics():
    """Display individual user statistics"""
    st.markdown("#### Individual User Statistics")
    
    try:
        users_result = supabase.table('users').select("email, name").execute()
        logs_result = supabase.table('query_logs').select("user_email, task_type, success, created_at").execute()
        
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
                
                user_stats.append((email, name, total, success, last_activity, user_logs))
            
            # Sort by total queries
            user_stats.sort(key=lambda x: x[2], reverse=True)
            
            # Display each user's stats
            for email, name, total, success, last_activity, user_logs in user_stats:
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