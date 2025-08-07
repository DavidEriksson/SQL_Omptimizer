# utils.py
import re
import tiktoken
from datetime import datetime, timedelta
import streamlit as st

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

def estimate_tokens(text, model="gpt-4o"):
    enc = tiktoken.encoding_for_model(model)
    return len(enc.encode(text))

def init_session_state():
    defaults = {
        "logged_in": False,
        "user_email": None,
        "is_admin": False,
        "query_count": 0,
        "query_reset_time": datetime.now() + timedelta(hours=24),
        "current_page": "Home",
        "formatted_sql": None,
        "selected_history_query": None,
        "current_sql_query": "",
        "last_analytics_update": None,
        "cached_analytics": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
