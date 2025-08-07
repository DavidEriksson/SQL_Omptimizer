# database.py
from supabase import create_client
import bcrypt
import os

SUPABASE_URL = os.getenv("SUPABASE_URL") or st.secrets["SUPABASE_URL"]
SUPABASE_KEY = os.getenv("SUPABASE_KEY") or st.secrets["SUPABASE_KEY"]
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def init_db():
    return supabase

def add_user(supabase, email, name, password, is_admin=False):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    supabase.table("users").insert({
        "email": email,
        "name": name,
        "password": hashed_password,
        "admin": is_admin
    }).execute()

def get_user(supabase, email):
    res = supabase.table("users").select("*").eq("email", email).single().execute()
    return res.data if res.data else None

def verify_password(stored_password, provided_password):
    return bcrypt.checkpw(provided_password.encode(), stored_password.encode())

def log_query(supabase, user_email, task_type, query_length, tokens_used=None, success=True, error_message=None):
    supabase.table("query_logs").insert({
        "user_email": user_email,
        "task_type": task_type,
        "query_length": query_length,
        "tokens_used": tokens_used,
        "success": success,
        "error_message": error_message
    }).execute()

def save_query_to_history(supabase, user_email, query_text, task_type, result_text=None, query_name=None):
    res = supabase.table("query_history").insert({
        "user_email": user_email,
        "query_text": query_text,
        "task_type": task_type,
        "result_text": result_text,
        "query_name": query_name
    }).execute()
    return res.data[0]["id"] if res.data else None

def get_user_query_history(supabase, user_email, limit=50):
    res = supabase.table("query_history")\
        .select("id, query_text, task_type, result_text, is_favorite, query_name, timestamp")\
        .eq("user_email", user_email)\
        .order("timestamp", desc=True)\
        .limit(limit)\
        .execute()
    return res.data

def get_user_favorites(supabase, user_email):
    res = supabase.table("query_history")\
        .select("id, query_text, task_type, result_text, query_name, timestamp")\
        .eq("user_email", user_email)\
        .eq("is_favorite", True)\
        .order("timestamp", desc=True)\
        .execute()
    return res.data

def toggle_favorite(supabase, query_id):
    current = supabase.table("query_history").select("is_favorite").eq("id", query_id).single().execute()
    if not current.data:
        return None
    new_status = not current.data["is_favorite"]
    supabase.table("query_history").update({"is_favorite": new_status}).eq("id", query_id).execute()
    return new_status

def delete_query_from_history(supabase, query_id, user_email):
    res = supabase.table("query_history").delete().eq("id", query_id).eq("user_email", user_email).execute()
    return res.status_code == 200

def update_query_name(supabase, query_id, user_email, new_name):
    res = supabase.table("query_history")\
        .update({"query_name": new_name})\
        .eq("id", query_id)\
        .eq("user_email", user_email)\
        .execute()
    return res.status_code == 200
