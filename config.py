import streamlit as st
from supabase import create_client, Client

# === Load from Streamlit Secrets ===
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
ADMIN_EMAILS = st.secrets["ADMIN_EMAILS"]
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

# === Initialize Supabase Client ===
@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase: Client = init_supabase()

def init_page_config():
    """Initialize Streamlit page configuration"""
    st.set_page_config(
        page_title="SQL Optimizer AI",
        page_icon="",
        layout="wide",
        initial_sidebar_state="expanded"
    )

def apply_custom_css():
    """Apply custom CSS styling"""
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