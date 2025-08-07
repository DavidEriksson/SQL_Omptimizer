import streamlit as st
import bcrypt
from datetime import datetime, timedelta
from config import supabase

# === User Functions ===
def add_user(email, name, password, is_admin=False):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    try:
        data = {
            "email": email,
            "name": name,
            "password": hashed_password,
            "is_admin": is_admin
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

# === Query Functions ===
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

# === Analytics Functions ===
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

# === User Management Functions ===
def get_all_users():
    try:
        result = supabase.table('users').select("email, name, is_admin").execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error fetching users: {str(e)}")
        return []

def get_regular_users():
    try:
        result = supabase.table('users').select("email, name").eq('is_admin', False).execute()
        return result.data if result.data else []
    except Exception as e:
        st.error(f"Error fetching regular users: {str(e)}")
        return []

def grant_admin_access(email):
    try:
        supabase.table('users').update({"is_admin": True}).eq('email', email).execute()
        return True
    except Exception as e:
        st.error(f"Error granting admin access: {str(e)}")
        return False

def reset_user_password(email, new_password):
    try:
        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        supabase.table('users').update({"password": hashed_password}).eq('email', email).execute()
        return True
    except Exception as e:
        st.error(f"Error resetting password: {str(e)}")
        return False

def delete_user(email):
    try:
        supabase.table('users').delete().eq('email', email).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting user: {str(e)}")
        return False