
import json
import openai
from config import OPENAI_API_KEY
from database import log_query, save_query_to_history
import graphviz

def execution_plan_page():
    """Render the execution plan visualization page"""
    st.markdown("## Query Execution Plan Visualization")
    st.markdown("Understand how your SQL query will be executed by the database engine")
    
    # Database type selection
    col1, col2 = st.columns([3, 1])
    with col1:
        sql_query = st.text_area(
            "SQL Query",
            height=200,
            placeholder="Paste your SQL query here to visualize its execution plan...",
            value=st.session_state.get('selected_history_query', ''),
            key="execution_sql_input"
        )
    
    with col2:
        db_type = st.selectbox(
            "Database Type",
            ["PostgreSQL", "MySQL", "SQL Server", "Oracle", "SQLite"],
            help="Different databases have different execution strategies"
        )
        
        visualization_type = st.radio(
            "Visualization Style",
            ["Tree View", "Flow Chart", "Table View"],
            help="Choose how to display the execution plan"
        )
        
        analyze_button = st.button(
            "Generate Execution Plan",
            type="primary",
            use_container_width=True,
            disabled=(not st.session_state.is_admin and st.session_state.query_count >= 5)
        )
    
    # Clear selected query after using it
    if 'selected_history_query' in st.session_state:
        st.session_state.selected_history_query = None
    
    if analyze_button and sql_query:
        generate_execution_plan(sql_query, db_type, visualization_type)
    
    # Educational content
    with st.expander("Understanding Execution Plans"):
        show_educational_content()

def generate_execution_plan(sql_query, db_type, viz_type):
    """Generate and visualize the execution plan"""
    
    # Check usage limits
    if not st.session_state.is_admin and st.session_state.query_count >= 5:
        st.error("Daily query limit reached. Limit resets in 24 hours.")
        return
    
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""Analyze this SQL query and generate a detailed execution plan for {db_type}:

SQL Query:
{sql_query}

Provide a detailed execution plan including:
1. Query parsing and optimization steps
2. Table access methods (full scan, index scan, etc.)
3. Join algorithms (nested loop, hash join, merge join)
4. Filtering and sorting operations
5. Estimated costs and row counts
6. Potential bottlenecks

Format the response as a JSON object with this structure:
{{
    "steps": [
        {{
            "id": 1,
            "operation": "Table Scan",
            "table": "users",
            "details": "Full table scan on users table",
            "estimated_rows": 10000,
            "cost": 100,
            "parent_id": null
        }},
        ...
    ],
    "summary": {{
        "total_cost": 500,
        "execution_time_estimate": "~50ms",
        "main_bottleneck": "Full table scan on users",
        "optimization_suggestions": ["Create index on user_id", "..."]
    }},
    "warnings": ["Missing index on foreign key", "..."]
}}
"""
    
    with st.spinner("Analyzing query execution plan..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=2000
            )
            
            result = response.choices[0].message.content
            
            # Update usage count
            if not st.session_state.is_admin:
                st.session_state.query_count += 1
            
            # Log the query
            log_query(
                user_email=st.session_state.user_email,
                task_type="Execution Plan",
                query_length=len(sql_query),
                success=True
            )
            
            # Parse the JSON response
            try:
                # Extract JSON from the response
                json_start = result.find('{')
                json_end = result.rfind('}') + 1
                json_str = result[json_start:json_end]
                execution_plan = json.loads(json_str)
            except:
                # Fallback if JSON parsing fails
                execution_plan = parse_text_response(result)
            
            # Display the execution plan
            display_execution_plan(execution_plan, viz_type, sql_query)
            
        except Exception as e:
            st.error(f"Error generating execution plan: {str(e)}")
            log_query(
                user_email=st.session_state.user_email,
                task_type="Execution Plan",
                query_length=len(sql_query),
                success=False,
                error_message=str(e)
            )

def display_execution_plan(plan, viz_type, original_query):
    """Display the execution plan in the selected format"""
    
    # Summary metrics
    if 'summary' in plan:
        st.markdown("### Execution Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Cost", plan['summary'].get('total_cost', 'N/A'))
        with col2:
            st.metric("Est. Time", plan['summary'].get('execution_time_estimate', 'N/A'))
        with col3:
            st.metric("Steps", len(plan.get('steps', [])))
        with col4:
            bottleneck = plan['summary'].get('main_bottleneck', 'None identified')
            st.metric("Main Bottleneck", bottleneck[:20] + "..." if len(bottleneck) > 20 else bottleneck)
    
    # Warnings
    if 'warnings' in plan and plan['warnings']:
        st.warning("**Potential Issues:**")
        for warning in plan['warnings']:
            st.write(f"• {warning}")
    
    # Visualization
    st.markdown("### Execution Flow")
    
    if viz_type == "Tree View":
        display_tree_view(plan['steps'])
    elif viz_type == "Flow Chart":
        display_flow_chart(plan['steps'])
    else:  # Table View
        display_table_view(plan['steps'])
    
    # Optimization suggestions
    if 'summary' in plan and 'optimization_suggestions' in plan['summary']:
        with st.expander("Optimization Suggestions", expanded=True):
            for i, suggestion in enumerate(plan['summary']['optimization_suggestions'], 1):
                st.write(f"{i}. {suggestion}")
    
    # Save options
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Optimize This Query", use_container_width=True):
            st.session_state.selected_history_query = original_query
            st.session_state.current_page = "Optimizer"
            st.rerun()
    
    with col2:
        plan_text = format_plan_as_text(plan)
        st.download_button(
            "Download Plan",
            plan_text,
            file_name="execution_plan.txt",
            mime="text/plain",
            use_container_width=True
        )
    
    with col3:
        if st.button("Save to History", use_container_width=True):
            save_query_to_history(
                user_email=st.session_state.user_email,
                query_text=original_query,
                task_type="Execution Plan",
                result_text=plan_text,
                query_name=f"Execution Plan: {original_query[:30]}"
            )
            st.success("Saved to history!")

def display_tree_view(steps):
    """Display execution plan as a tree structure"""
    
    # Build tree structure
    tree_items = []
    for step in steps:
        indent = "  " * get_depth(step, steps)
        icon = get_operation_icon(step['operation'])
        cost_indicator = get_cost_indicator(step.get('cost', 0))
        
        tree_items.append(
            f"{indent}{icon} **{step['operation']}** {cost_indicator}\n"
            f"{indent}  └─ {step['details']}\n"
            f"{indent}     Rows: {step.get('estimated_rows', 'N/A')} | Cost: {step.get('cost', 'N/A')}"
        )
    
    st.code("\n".join(tree_items), language="text")

def display_flow_chart(steps):
    """Display execution plan as a flow chart using graphviz"""
    
    try:
        # Create a graphviz graph
        dot = graphviz.Digraph(comment='Execution Plan')
        dot.attr(rankdir='TB')
        dot.attr('node', shape='box', style='rounded,filled', fillcolor='lightblue')
        
        # Add nodes
        for step in steps:
            label = f"{step['operation']}\n{step.get('table', '')}\nRows: {step.get('estimated_rows', '?')}\nCost: {step.get('cost', '?')}"
            
            # Color based on cost
            cost = step.get('cost', 0)
            if cost > 500:
                color = 'red'
            elif cost > 100:
                color = 'orange'
            else:
                color = 'lightgreen'
            
            dot.node(str(step['id']), label, fillcolor=color)
        
        # Add edges
        for step in steps:
            if step.get('parent_id'):
                dot.edge(str(step['parent_id']), str(step['id']))
        
        # Render the graph
        st.graphviz_chart(dot.source)
        
    except Exception as e:
        st.error(f"Could not generate flow chart: {str(e)}")
        # Fallback to tree view
        display_tree_view(steps)

def display_table_view(steps):
    """Display execution plan as a table"""
    
    import pandas as pd
    
    # Prepare data for dataframe
    data = []
    for step in steps:
        data.append({
            'Step': step['id'],
            'Operation': step['operation'],
            'Table': step.get('table', '-'),
            'Details': step['details'][:50] + '...' if len(step['details']) > 50 else step['details'],
            'Est. Rows': step.get('estimated_rows', 'N/A'),
            'Cost': step.get('cost', 'N/A'),
            'Parent': step.get('parent_id', '-')
        })
    
    df = pd.DataFrame(data)
    
    # Display with conditional formatting
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cost": st.column_config.NumberColumn(
                "Cost",
                help="Estimated cost of this operation",
                format="%d"
            ),
            "Est. Rows": st.column_config.NumberColumn(
                "Est. Rows",
                help="Estimated number of rows",
                format="%d"
            )
        }
    )

def show_educational_content():
    """Show educational content about execution plans"""
    
    st.markdown("""
    ### What is an Execution Plan?
    
    An execution plan shows how a database engine will execute your SQL query. It reveals:
    
    **Key Operations:**
    - **Table Scan**: Reading entire table (slow for large tables)
    - **Index Scan**: Using an index to find rows (faster)
    - **Nested Loop Join**: Simple join, good for small datasets
    - **Hash Join**: Fast for large datasets with equality conditions
    - **Sort**: Ordering results (can be expensive)
    
    **Cost Indicators:**
    - 🟢 **Low Cost (0-100)**: Efficient operation
    - 🟡 **Medium Cost (100-500)**: May need optimization
    - 🔴 **High Cost (500+)**: Bottleneck, needs attention
    
    **Common Optimizations:**
    1. **Add Indexes**: Speed up searches and joins
    2. **Rewrite Subqueries**: Convert to joins when possible
    3. **Limit Early**: Filter data as soon as possible
    4. **Use Appropriate Joins**: Choose the right join type
    5. **Avoid SELECT ***: Only fetch needed columns
    
    **Reading the Visualization:**
    - Flow goes from bottom to top (or left to right)
    - Wider arrows = more data flowing
    - Red nodes = expensive operations
    - Numbers show estimated rows and costs
    """)

# Helper functions
def get_operation_icon(operation):
    """Get icon for operation type"""
    operation_lower = operation.lower()
    if 'scan' in operation_lower:
        return '[SCAN]'
    elif 'index' in operation_lower:
        return '[INDEX]'
    elif 'join' in operation_lower:
        return '[JOIN]'
    elif 'sort' in operation_lower:
        return '[SORT]'
    elif 'filter' in operation_lower or 'where' in operation_lower:
        return '[FILTER]'
    elif 'aggregate' in operation_lower or 'group' in operation_lower:
        return '[AGG]'
    else:
        return '[OP]'

def get_cost_indicator(cost):
    """Get visual indicator for cost"""
    if cost > 500:
        return '🔴'
    elif cost > 100:
        return '🟡'
    else:
        return '🟢'

def get_depth(step, all_steps):
    """Calculate depth of step in tree"""
    depth = 0
    current = step
    while current.get('parent_id'):
        depth += 1
        parent_id = current.get('parent_id')
        current = next((s for s in all_steps if s['id'] == parent_id), None)
        if not current:
            break
    return depth

def parse_text_response(text):
    """Parse text response if JSON parsing fails"""
    # Fallback parser for non-JSON responses
    return {
        "steps": [
            {
                "id": 1,
                "operation": "Query Execution",
                "table": "multiple",
                "details": "See analysis below",
                "estimated_rows": "N/A",
                "cost": "N/A",
                "parent_id": None
            }
        ],
        "summary": {
            "total_cost": "N/A",
            "execution_time_estimate": "N/A",
            "main_bottleneck": "Analysis in progress",
            "optimization_suggestions": [text]
        },
        "warnings": []
    }

def format_plan_as_text(plan):
    """Format execution plan as readable text"""
    lines = []
    lines.append("EXECUTION PLAN ANALYSIS")
    lines.append("=" * 50)
    
    if 'summary' in plan:
        lines.append("\nSUMMARY:")
        lines.append(f"Total Cost: {plan['summary'].get('total_cost', 'N/A')}")
        lines.append(f"Estimated Time: {plan['summary'].get('execution_time_estimate', 'N/A')}")
        lines.append(f"Main Bottleneck: {plan['summary'].get('main_bottleneck', 'N/A')}")
    
    lines.append("\nEXECUTION STEPS:")
    for step in plan.get('steps', []):
        lines.append(f"\nStep {step['id']}: {step['operation']}")
        if 'table' in step:
            lines.append(f"  Table: {step['table']}")
        lines.append(f"  Details: {step['details']}")
        lines.append(f"  Estimated Rows: {step.get('estimated_rows', 'N/A')}")
        lines.append(f"  Cost: {step.get('cost', 'N/A')}")
    
    if 'warnings' in plan and plan['warnings']:
        lines.append("\nWARNINGS:")
        for warning in plan['warnings']:
            lines.append(f"- {warning}")
    
    if 'summary' in plan and 'optimization_suggestions' in plan['summary']:
        lines.append("\nOPTIMIZATION SUGGESTIONS:")
        for i, suggestion in enumerate(plan['summary']['optimization_suggestions'], 1):
            lines.append(f"{i}. {suggestion}")
    
    return "\n".join(lines)