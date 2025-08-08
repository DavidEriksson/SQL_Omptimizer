import streamlit as st
import openai
import pandas as pd
import plotly.graph_objects as go
import difflib
from config import OPENAI_API_KEY
from database import log_query, save_query_to_history, get_user_query_history
from utils import get_prompt_templates

def comparison_page():
    """Render the query comparison page"""
    st.markdown("## Query Performance Comparison")
    st.markdown("Compare different versions of your SQL queries to see improvements")
    
    # Input method selection
    input_method = st.radio(
        "How would you like to input queries?",
        ["Manual Input", "From History", "Original + AI Optimized"],
        horizontal=True
    )
    
    query_a, query_b, label_a, label_b = get_queries_for_comparison(input_method)
    
    if query_a and query_b:
        # Comparison options
        with st.expander("Comparison Settings", expanded=False):
            col1, col2 = st.columns(2)
            with col1:
                db_type = st.selectbox(
                    "Database Type", 
                    ["PostgreSQL", "MySQL", "SQL Server", "Oracle", "SQLite"]
                )
            with col2:
                comparison_depth = st.select_slider(
                    "Analysis Depth",
                    options=["Basic", "Standard", "Detailed"],
                    value="Standard"
                )
            
            comparison_aspects = st.multiselect(
                "What to compare?",
                ["Execution Plan", "Performance Metrics", "Index Usage", 
                 "Join Efficiency", "Code Structure", "Resource Usage"],
                default=["Execution Plan", "Performance Metrics"]
            )
            
            show_recommendations = st.checkbox("Show improvement recommendations", True)
        
        # Run comparison
        if st.button("Compare Queries", type="primary", use_container_width=True):
            if not st.session_state.is_admin and st.session_state.query_count >= 5:
                st.error("Daily query limit reached. Limit resets in 24 hours.")
            else:
                run_comparison(
                    query_a, query_b, label_a, label_b,
                    db_type, comparison_aspects, 
                    show_recommendations, comparison_depth
                )

def get_queries_for_comparison(input_method):
    """Get queries based on selected input method"""
    query_a = None
    query_b = None
    label_a = "Query A"
    label_b = "Query B"
    
    if input_method == "Manual Input":
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### Query Version A")
            query_a = st.text_area(
                "First Query",
                height=300,
                placeholder="Paste your original query here...",
                key="query_a_input"
            )
            label_a = st.text_input("Label (optional)", value="Original", key="label_a")
            
        with col2:
            st.markdown("### Query Version B")
            query_b = st.text_area(
                "Second Query",
                height=300,
                placeholder="Paste your optimized query here...",
                key="query_b_input"
            )
            label_b = st.text_input("Label (optional)", value="Optimized", key="label_b")
    
    elif input_method == "From History":
        history = get_user_query_history(st.session_state.user_email, limit=20)
        
        if history:
            col1, col2 = st.columns(2)
            
            query_options = [
                f"{item['task_type']} - {item.get('query_name', item['created_at'][:10])}"
                for item in history
            ]
            
            with col1:
                st.markdown("### Select First Query")
                selected_a = st.selectbox(
                    "Query A",
                    range(len(query_options)),
                    format_func=lambda x: query_options[x],
                    key="history_a"
                )
                if selected_a is not None:
                    query_a = history[selected_a]['query_text']
                    label_a = query_options[selected_a]
                    with st.expander("Preview Query A"):
                        st.code(query_a, language="sql")
            
            with col2:
                st.markdown("### Select Second Query")
                selected_b = st.selectbox(
                    "Query B",
                    range(len(query_options)),
                    format_func=lambda x: query_options[x],
                    key="history_b"
                )
                if selected_b is not None:
                    query_b = history[selected_b]['query_text']
                    label_b = query_options[selected_b]
                    with st.expander("Preview Query B"):
                        st.code(query_b, language="sql")
        else:
            st.info("No queries in history. Try analyzing some queries first!")
    
    else:  # Original + AI Optimized
        st.markdown("### Original Query")
        query_a = st.text_area(
            "Enter your query to optimize",
            height=200,
            placeholder="Paste your SQL query here...",
            key="original_query"
        )
        label_a = "Original"
        
        if query_a and st.button("Generate Optimized Version", type="secondary"):
            with st.spinner("Generating optimized query..."):
                query_b = generate_optimized_query(query_a)
                if query_b:
                    st.session_state.optimized_query = query_b
        
        if 'optimized_query' in st.session_state:
            st.markdown("### Generated Optimized Query")
            query_b = st.text_area(
                "Review and edit if needed",
                value=st.session_state.optimized_query,
                height=200,
                key="optimized_query_display"
            )
            label_b = "AI Optimized"
    
    return query_a, query_b, label_a, label_b

def generate_optimized_query(original_query):
    """Generate an optimized version of the query using AI"""
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""Optimize this SQL query for better performance.
    
Original Query:
{original_query}

Provide ONLY the optimized SQL query without any explanation.
Focus on:
- Eliminating unnecessary subqueries
- Using appropriate joins
- Adding useful indexes hints
- Reducing data scanned
- Improving filter conditions

Return only the SQL code, nothing else."""
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Error generating optimized query: {str(e)}")
        return None

def run_comparison(query_a, query_b, label_a, label_b, db_type, 
                   comparison_aspects, show_recommendations, comparison_depth):
    """Run the comparison analysis"""
    
    if not st.session_state.is_admin:
        st.session_state.query_count += 1
    
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = create_comparison_prompt(
        query_a, query_b, db_type, 
        comparison_aspects, comparison_depth
    )
    
    with st.spinner("Analyzing queries..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=3000
            )
            
            result = response.choices[0].message.content
            
            # Log the comparison
            log_query(
                user_email=st.session_state.user_email,
                task_type="Query Comparison",
                query_length=len(query_a) + len(query_b),
                success=True
            )
            
            # Parse and display results
            comparison_results = parse_comparison_results(result)
            display_comparison_results(
                comparison_results, query_a, query_b, 
                label_a, label_b, show_recommendations
            )
            
            # Save option
            if st.button("Save Comparison to History"):
                comparison_text = f"Comparison: {label_a} vs {label_b}\n\n{result}"
                save_query_to_history(
                    user_email=st.session_state.user_email,
                    query_text=f"{query_a}\n---VS---\n{query_b}",
                    task_type="Comparison",
                    result_text=comparison_text,
                    query_name=f"Compare: {label_a} vs {label_b}"
                )
                st.success("Comparison saved to history!")
                
        except Exception as e:
            st.error(f"Error during comparison: {str(e)}")
            log_query(
                user_email=st.session_state.user_email,
                task_type="Query Comparison",
                query_length=len(query_a) + len(query_b),
                success=False,
                error_message=str(e)
            )

def create_comparison_prompt(query_a, query_b, db_type, aspects, depth):
    """Create the comparison analysis prompt"""
    
    depth_instructions = {
        "Basic": "Provide a quick overview of the main differences.",
        "Standard": "Provide a balanced analysis with key metrics and recommendations.",
        "Detailed": "Provide an exhaustive analysis with all possible metrics and detailed explanations."
    }
    
    aspects_str = ", ".join(aspects)
    
    return f"""Compare these two SQL queries for {db_type} database.

Query A:
{query_a}

Query B:
{query_b}

Analysis depth: {depth} - {depth_instructions[depth]}
Focus on: {aspects_str}

Provide a structured comparison including:

1. PERFORMANCE METRICS
- Estimated execution time for each query
- Cost comparison (use numbers)
- Rows processed comparison
- Memory usage estimation
- I/O operations comparison

2. EXECUTION PLAN DIFFERENCES
- Key operations that differ
- Join methods comparison
- Index usage differences
- Scan types (full vs index)

3. CODE STRUCTURE ANALYSIS
- Complexity comparison
- Readability assessment
- Maintainability factors
- Best practices adherence

4. WINNER DETERMINATION
- Which query is better overall
- Percentage improvement (if any)
- Specific scenarios where each might be preferred

5. RECOMMENDATIONS
- How to further optimize the better query
- What to avoid from the worse query
- General insights learned

Format your response with clear sections and use specific numbers where possible.
"""

def parse_comparison_results(result_text):
    """Parse the AI response into structured data"""
    # This is a simplified parser - enhance based on actual response format
    results = {
        'raw_text': result_text,
        'performance_improvement': 0,
        'cost_reduction': 0,
        'rows_reduction': 0,
        'winner': 'Unknown',
        'sections': {}
    }
    
    # Extract metrics from text (simplified)
    import re
    
    # Look for percentage improvements
    perf_match = re.search(r'(\d+)%\s*(?:faster|improvement|better)', result_text, re.IGNORECASE)
    if perf_match:
        results['performance_improvement'] = int(perf_match.group(1))
    
    # Look for cost numbers
    cost_match = re.search(r'cost.*?(\d+).*?vs.*?(\d+)', result_text, re.IGNORECASE)
    if cost_match:
        cost_a = int(cost_match.group(1))
        cost_b = int(cost_match.group(2))
        if cost_a > 0:
            results['cost_reduction'] = int(((cost_a - cost_b) / cost_a) * 100)
    
    # Determine winner
    if 'query b' in result_text.lower() and 'better' in result_text.lower():
        results['winner'] = 'Query B'
    elif 'query a' in result_text.lower() and 'better' in result_text.lower():
        results['winner'] = 'Query A'
    
    # Split into sections
    sections = result_text.split('\n\n')
    for i, section in enumerate(sections):
        if section.strip():
            results['sections'][f'section_{i}'] = section
    
    return results

def display_comparison_results(results, query_a, query_b, label_a, label_b, show_recommendations):
    """Display the comparison results"""
    
    # Summary metrics
    st.markdown("### Performance Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        improvement = results.get('performance_improvement', 0)
        if improvement > 0:
            st.metric(
                "Performance Gain",
                f"{improvement}%",
                delta="Faster"
            )
        elif improvement < 0:
            st.metric(
                "Performance Loss",
                f"{abs(improvement)}%",
                delta="Slower"
            )
        else:
            st.metric("Performance", "Similar")
    
    with col2:
        cost_reduction = results.get('cost_reduction', 0)
        if cost_reduction != 0:
            st.metric(
                "Cost Change",
                f"{abs(cost_reduction)}%",
                delta="Lower" if cost_reduction > 0 else "Higher"
            )
        else:
            st.metric("Cost Change", "None")
    
    with col3:
        st.metric("Better Query", results.get('winner', 'Undetermined'))
    
    with col4:
        complexity_score = len(query_b) - len(query_a)
        st.metric(
            "Complexity",
            "Simpler" if complexity_score < -10 else "Similar" if abs(complexity_score) <= 10 else "More Complex"
        )
    
    # Detailed comparison tabs
    tab1, tab2, tab3, tab4 = st.tabs(
        ["Analysis Results", "Code Differences", "Visual Comparison", "Recommendations"]
    )
    
    with tab1:
        display_analysis_results(results)
    
    with tab2:
        display_code_diff(query_a, query_b, label_a, label_b)
    
    with tab3:
        display_visual_comparison(results, label_a, label_b)
    
    with tab4:
        if show_recommendations:
            display_recommendations(results)

def display_analysis_results(results):
    """Display the detailed analysis text"""
    st.markdown(results['raw_text'])

def display_code_diff(query_a, query_b, label_a, label_b):
    """Display code differences between queries"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown(f"#### {label_a}")
        st.code(query_a, language="sql")
    
    with col2:
        st.markdown(f"#### {label_b}")
        st.code(query_b, language="sql")
    
    # Show unified diff
    st.markdown("#### Differences")
    
    diff = difflib.unified_diff(
        query_a.splitlines(keepends=True),
        query_b.splitlines(keepends=True),
        fromfile=label_a,
        tofile=label_b,
        lineterm=''
    )
    
    diff_text = ''.join(diff)
    if diff_text:
        st.code(diff_text, language="diff")
    else:
        st.info("Queries are identical")

def display_visual_comparison(results, label_a, label_b):
    """Display visual charts comparing the queries"""
    
    # Create comparison chart
    if results.get('performance_improvement') or results.get('cost_reduction'):
        metrics = ['Performance', 'Cost', 'Complexity']
        
        # Normalize values for visualization (using 100 as baseline for Query A)
        values_a = [100, 100, 100]
        improvement = results.get('performance_improvement', 0)
        cost_reduction = results.get('cost_reduction', 0)
        
        values_b = [
            100 - improvement,  # Lower is better for performance
            100 - cost_reduction,  # Lower is better for cost
            100  # Placeholder for complexity
        ]
        
        fig = go.Figure(data=[
            go.Bar(name=label_a, x=metrics, y=values_a),
            go.Bar(name=label_b, x=metrics, y=values_b)
        ])
        
        fig.update_layout(
            title="Query Comparison (Lower is Better)",
            barmode='group',
            yaxis_title="Relative Score",
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    # Winner indicator
    winner = results.get('winner', 'Undetermined')
    if winner != 'Undetermined':
        st.success(f"**{winner}** performs better overall")
    else:
        st.info("Performance comparison is inconclusive")

def display_recommendations(results):
    """Display recommendations from the analysis"""
    
    # Extract recommendations from the raw text
    raw_text = results.get('raw_text', '')
    
    if 'RECOMMENDATIONS' in raw_text.upper():
        # Find recommendations section
        rec_start = raw_text.upper().find('RECOMMENDATIONS')
        if rec_start != -1:
            recommendations_text = raw_text[rec_start:]
            st.markdown(recommendations_text)
    else:
        st.info("No specific recommendations were generated. Consider running a more detailed analysis.")
    
    # General optimization tips
    with st.expander("General Optimization Tips"):
        st.markdown("""
        **Common optimization strategies:**
        
        1. **Index Usage**: Ensure queries use appropriate indexes
        2. **Join Order**: Place smaller tables first in joins
        3. **Filter Early**: Apply WHERE conditions as early as possible
        4. **Avoid Subqueries**: Replace with JOINs when possible
        5. **Limit Results**: Use LIMIT when you don't need all rows
        6. **Column Selection**: Select only needed columns, avoid SELECT *
        7. **Statistics**: Keep database statistics updated
        8. **Query Cache**: Utilize query caching when available
        """)

# Add export functionality
def export_comparison_report(results, query_a, query_b, label_a, label_b):
    """Export comparison results as a formatted report"""
    
    report = f"""
SQL QUERY COMPARISON REPORT
{'=' * 50}

{label_a} vs {label_b}

SUMMARY
-------
Winner: {results.get('winner', 'Undetermined')}
Performance Improvement: {results.get('performance_improvement', 0)}%
Cost Reduction: {results.get('cost_reduction', 0)}%

QUERY A: {label_a}
{'-' * 30}
{query_a}

QUERY B: {label_b}
{'-' * 30}
{query_b}

DETAILED ANALYSIS
{'-' * 30}
{results.get('raw_text', 'No analysis available')}

Generated on: {pd.Timestamp.now()}
    """
    
    return report