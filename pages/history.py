import streamlit as st
from database import (
    get_user_query_history, 
    get_user_favorites, 
    toggle_favorite, 
    delete_query_from_history, 
    update_query_name
)

def history_page():
    """Render the query history page"""
    st.markdown("## Query History")
    
    history = get_user_query_history(st.session_state.user_email)
    favorites = get_user_favorites(st.session_state.user_email)
    
    tab1, tab2 = st.tabs(["Recent Queries", "Favorites"])
    
    with tab1:
        display_recent_queries(history)
    
    with tab2:
        display_favorite_queries(favorites)

def display_recent_queries(history):
    """Display recent queries with search and filter"""
    st.markdown("### Your Recent Queries")
    
    if not history:
        st.info("No query history yet. Start by analyzing some SQL queries!")
        return
    
    # Search and filter controls
    col_search1, col_search2 = st.columns([2, 1])
    with col_search1:
        search_term = st.text_input("Search queries:", placeholder="Search by SQL content or name...")
    with col_search2:
        task_filter = st.selectbox("Filter by task:", ["All", "Explain", "Optimize", "Detect Issues", "Test"])
    
    # Filter history
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
    
    if not filtered_history:
        if search_term or task_filter != "All":
            st.info("No queries match your search criteria.")
        else:
            st.info("No queries found.")
        return
    
    st.caption(f"Showing {len(filtered_history)} of {len(history)} queries")
    
    # Display filtered queries
    for item in filtered_history:
        display_query_item(item)

def display_favorite_queries(favorites):
    """Display favorite queries"""
    st.markdown("### Your Favorite Queries")
    
    if not favorites:
        st.info("No favorite queries yet. Star some queries from your history to see them here!")
        return
    
    st.caption(f"{len(favorites)} favorite queries")
    
    for item in favorites:
        display_query_item(item, is_favorite_tab=True)

def display_query_item(item, is_favorite_tab=False):
    """Display a single query item"""
    star_mark = "[Favorite] " if item.get('is_favorite') else ""
    display_name = item.get('query_name') if item.get('query_name') else f"{item['task_type']} - {item['created_at'][:10]}"
    
    with st.expander(f"{star_mark}{display_name}", expanded=False):
        # Query details
        col_details1, col_details2, col_details3 = st.columns([2, 1, 1])
        
        with col_details1:
            st.markdown(f"**Task:** {item['task_type']}")
            st.markdown(f"**Date:** {item['created_at']}")
        
        with col_details2:
            st.markdown(f"**Length:** {len(item['query_text'])} chars")
            if item.get('query_name'):
                st.markdown(f"**Name:** {item['query_name']}")
        
        with col_details3:
            display_query_actions(item, is_favorite_tab)
        
        # Rename functionality for favorites
        if is_favorite_tab:
            col_rename1, col_rename2 = st.columns([2, 1])
            with col_rename1:
                new_name = st.text_input("Rename:", value=item.get('query_name', ''), key=f"rename_{item['id']}")
            with col_rename2:
                if st.button("Update Name", key=f"update_{item['id']}"):
                    if update_query_name(item['id'], st.session_state.user_email, new_name.strip()):
                        st.success("Name updated!")
                        st.rerun()
        
        # Display SQL query
        st.markdown("**SQL Query:**")
        st.code(item['query_text'], language="sql")
        
        # Display results if available
        if item.get('result_text'):
            with st.expander("View Analysis Result"):
                st.markdown(item['result_text'])

def display_query_actions(item, is_favorite_tab):
    """Display action buttons for a query item"""
    if is_favorite_tab:
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Use", key=f"use_fav_{item['id']}"):
                st.session_state.selected_history_query = item['query_text']
                st.session_state.current_page = "Optimizer"
                st.rerun()
        with col_btn2:
            if st.button("Unfav", key=f"unfav_{item['id']}", type="secondary"):
                toggle_favorite(item['id'])
                st.rerun()
    else:
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