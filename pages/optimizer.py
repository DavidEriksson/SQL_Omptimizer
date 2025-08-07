import streamlit as st
import openai
import tiktoken
from config import OPENAI_API_KEY
from database import log_query, save_query_to_history, update_query_name
from utils import format_sql, get_prompt_templates

def optimizer_page():
    """Render the SQL optimizer page"""
    st.markdown("## SQL Query Optimizer")
    
    st.markdown('<div class="query-container">', unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        sql_query = render_sql_input()
    
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
        analyze_query(sql_query, task)

def render_sql_input():
    """Render the SQL input text area"""
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
    
    return sql_query

def analyze_query(sql_query, task):
    """Analyze the SQL query using OpenAI"""
    if not sql_query.strip():
        st.error("Please enter a SQL query.")
        return
    
    if not st.session_state.is_admin and st.session_state.query_count >= 5:
        st.error("Daily query limit reached. Limit resets in 24 hours.")
        return
    
    if not st.session_state.is_admin:
        st.session_state.query_count += 1
    
    model = "gpt-4o-mini"
    temperature = 0.3
    max_tokens = 1500
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    def estimate_tokens(text):
        enc = tiktoken.encoding_for_model(model)
        return len(enc.encode(text))
    
    prompt = get_prompt_templates(sql_query, task)
    
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
            
            display_results(task, reply, token_estimate, model, history_id)
            
        except Exception as e:
            log_query(user_email=st.session_state.user_email, task_type=task, 
                     query_length=len(sql_query), success=False, error_message=str(e))
            st.error(f"Error: {str(e)}")

def display_results(task, reply, token_estimate, model, history_id):
    """Display the analysis results"""
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