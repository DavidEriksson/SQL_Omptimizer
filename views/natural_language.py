import streamlit as st
import openai
from config import OPENAI_API_KEY, supabase
from database import log_query, save_query_to_history

# Sample schemas for quick start
SAMPLE_SCHEMAS = {
    "E-commerce": """
CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100) UNIQUE,
    city VARCHAR(100),
    state VARCHAR(50),
    country VARCHAR(50),
    created_at TIMESTAMP
);

CREATE TABLE products (
    product_id INT PRIMARY KEY,
    product_name VARCHAR(200),
    category VARCHAR(100),
    price DECIMAL(10,2),
    stock_quantity INT,
    created_at TIMESTAMP
);

CREATE TABLE orders (
    order_id INT PRIMARY KEY,
    customer_id INT REFERENCES customers(customer_id),
    order_date TIMESTAMP,
    total_amount DECIMAL(10,2),
    status VARCHAR(50)
);

CREATE TABLE order_items (
    order_item_id INT PRIMARY KEY,
    order_id INT REFERENCES orders(order_id),
    product_id INT REFERENCES products(product_id),
    quantity INT,
    unit_price DECIMAL(10,2)
);
""",
    "HR Database": """
CREATE TABLE employees (
    employee_id INT PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100),
    hire_date DATE,
    job_title VARCHAR(100),
    salary DECIMAL(10,2),
    department_id INT,
    manager_id INT
);

CREATE TABLE departments (
    department_id INT PRIMARY KEY,
    department_name VARCHAR(100),
    location VARCHAR(100)
);

CREATE TABLE attendance (
    attendance_id INT PRIMARY KEY,
    employee_id INT REFERENCES employees(employee_id),
    date DATE,
    check_in TIME,
    check_out TIME,
    status VARCHAR(20)
);
""",
    "School Database": """
CREATE TABLE students (
    student_id INT PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100),
    enrollment_date DATE,
    grade_level INT
);

CREATE TABLE courses (
    course_id INT PRIMARY KEY,
    course_name VARCHAR(100),
    credits INT,
    department VARCHAR(50)
);

CREATE TABLE enrollments (
    enrollment_id INT PRIMARY KEY,
    student_id INT REFERENCES students(student_id),
    course_id INT REFERENCES courses(course_id),
    semester VARCHAR(20),
    grade VARCHAR(2)
);

CREATE TABLE teachers (
    teacher_id INT PRIMARY KEY,
    first_name VARCHAR(50),
    last_name VARCHAR(50),
    email VARCHAR(100),
    department VARCHAR(50)
);
"""
}

def natural_language_page():
    """Render the natural language to SQL page"""
    st.markdown("## Natural Language to SQL")
    st.markdown("Ask questions in plain English and get SQL queries automatically generated!")
    
    # Check if user has a saved schema
    user_schema = load_user_schema()
    
    # Schema setup section
    with st.expander("📋 Database Schema Setup", expanded=(user_schema is None)):
        setup_schema()
    
    # Display current schema if exists
    if user_schema:
        with st.expander("📊 Current Schema", expanded=False):
            st.code(user_schema, language="sql")
            if st.button("Clear Schema", type="secondary"):
                clear_user_schema()
                st.rerun()
    
    # Natural language input section
    if user_schema:
        st.markdown("### Ask Your Question")
        
        # Example questions based on schema type
        show_example_questions(user_schema)
        
        # Input area
        nl_query = st.text_area(
            "Type your question in plain English:",
            placeholder="E.g., Show me all customers from New York who made orders last month",
            height=100
        )
        
        col1, col2 = st.columns([1, 4])
        with col1:
            include_explanation = st.checkbox("Explain query", value=True)
        
        if st.button("Generate SQL", type="primary", use_container_width=True):
            if nl_query:
                generate_sql_from_nl(nl_query, user_schema, include_explanation)
            else:
                st.warning("Please enter a question")
    else:
        st.info("👆 Please set up your database schema first to start using Natural Language queries")

def setup_schema():
    """Schema setup interface"""
    st.markdown("#### Choose how to provide your database schema:")
    
    tab1, tab2, tab3 = st.tabs(["Use Sample Schema", "Paste Your Schema", "Upload SQL File"])
    
    with tab1:
        st.markdown("##### Quick Start with Sample Schemas")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_sample = st.selectbox(
                "Select a sample schema:",
                options=list(SAMPLE_SCHEMAS.keys()),
                help="Choose a pre-built schema to get started quickly"
            )
        
        with col2:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("Use This Schema", use_container_width=True):
                save_user_schema(SAMPLE_SCHEMAS[selected_sample])
                st.success(f"✅ {selected_sample} schema loaded!")
                st.rerun()
        
        # Show preview of selected schema
        st.markdown("##### Preview:")
        st.code(SAMPLE_SCHEMAS[selected_sample], language="sql", height=300)
    
    with tab2:
        st.markdown("##### Paste Your CREATE TABLE Statements")
        
        schema_input = st.text_area(
            "Paste your schema here:",
            placeholder="""CREATE TABLE your_table (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    ...
);""",
            height=400
        )
        
        if st.button("Save Schema", use_container_width=True):
            if schema_input.strip():
                if validate_schema(schema_input):
                    save_user_schema(schema_input)
                    st.success("✅ Schema saved successfully!")
                    st.rerun()
                else:
                    st.error("Invalid schema format. Please check your CREATE TABLE statements.")
            else:
                st.warning("Please paste your schema")
    
    with tab3:
        st.markdown("##### Upload SQL File")
        
        uploaded_file = st.file_uploader(
            "Choose a SQL file",
            type=['sql', 'txt'],
            help="Upload a file containing your CREATE TABLE statements"
        )
        
        if uploaded_file is not None:
            schema_content = uploaded_file.read().decode("utf-8")
            st.markdown("##### Preview:")
            st.code(schema_content, language="sql", height=300)
            
            if st.button("Use This Schema", use_container_width=True):
                if validate_schema(schema_content):
                    save_user_schema(schema_content)
                    st.success("✅ Schema uploaded successfully!")
                    st.rerun()
                else:
                    st.error("Invalid schema format in file.")

def generate_sql_from_nl(nl_query, schema, include_explanation):
    """Generate SQL from natural language query"""
    
    # Check usage limits for non-admin users
    if not st.session_state.is_admin and st.session_state.query_count >= 5:
        st.error("Daily query limit reached. Limit resets in 24 hours.")
        return
    
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    
    prompt = f"""Given the following database schema:

{schema}

Convert this natural language query to SQL:
"{nl_query}"

Requirements:
1. Generate syntactically correct SQL
2. Use only tables and columns that exist in the schema
3. Make reasonable assumptions for ambiguous requests
4. If the query cannot be answered with the given schema, explain why

{"Also provide a brief explanation of what the query does." if include_explanation else ""}

Format your response as:
SQL:
```sql
[your SQL query here]
```

{"Explanation: [brief explanation of what the query does]" if include_explanation else ""}

If there are any assumptions made, list them as:
Assumptions: [list any assumptions]
"""
    
    with st.spinner("🤔 Generating SQL query..."):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )
            
            result = response.choices[0].message.content
            
            # Update usage count for non-admin users
            if not st.session_state.is_admin:
                st.session_state.query_count += 1
            
            # Log the query
            log_query(
                user_email=st.session_state.user_email,
                task_type="Natural Language",
                query_length=len(nl_query),
                success=True
            )
            
            # Display results
            st.markdown("### Generated SQL Query")
            
            # Parse and display the SQL
            if "```sql" in result:
                sql_start = result.find("```sql") + 6
                sql_end = result.find("```", sql_start)
                sql_query = result[sql_start:sql_end].strip()
            else:
                # Fallback if formatting is different
                sql_query = extract_sql_from_response(result)
            
            st.code(sql_query, language="sql")
            
            # Display explanation and assumptions if present
            if "Explanation:" in result:
                explanation = result.split("Explanation:")[1].split("Assumptions:")[0].strip()
                st.markdown("**Explanation:**")
                st.write(explanation)
            
            if "Assumptions:" in result:
                assumptions = result.split("Assumptions:")[1].strip()
                st.info(f"**Assumptions made:** {assumptions}")
            
            # Action buttons
            col1, col2, col3 = st.columns(3)
            
            with col1:
                if st.button("🔍 Analyze This Query", use_container_width=True):
                    st.session_state.selected_history_query = sql_query
                    st.session_state.current_page = "Optimizer"
                    st.rerun()
            
            with col2:
                if st.button("💾 Save to History", use_container_width=True):
                    save_query_to_history(
                        user_email=st.session_state.user_email,
                        query_text=sql_query,
                        task_type="Natural Language",
                        result_text=f"Generated from: {nl_query}",
                        query_name=f"NL: {nl_query[:50]}"
                    )
                    st.success("Saved to history!")
            
            with col3:
                st.download_button(
                    "📥 Download SQL",
                    sql_query,
                    file_name="generated_query.sql",
                    mime="text/plain",
                    use_container_width=True
                )
            
        except Exception as e:
            st.error(f"Error generating SQL: {str(e)}")
            log_query(
                user_email=st.session_state.user_email,
                task_type="Natural Language",
                query_length=len(nl_query),
                success=False,
                error_message=str(e)
            )

def show_example_questions(schema):
    """Show example questions based on the schema"""
    
    # Detect schema type based on content
    examples = []
    
    if "customers" in schema.lower() or "orders" in schema.lower():
        examples = [
            "Show me all customers from California",
            "What are the top 10 best-selling products?",
            "Find all orders from last month over $1000",
            "Which customers haven't made any orders?",
            "Calculate total revenue by product category"
        ]
    elif "employees" in schema.lower() or "departments" in schema.lower():
        examples = [
            "List all employees in the IT department",
            "Who are the top 5 highest paid employees?",
            "Show employees who have been here more than 5 years",
            "Find all employees who report to John Smith",
            "What is the average salary by department?"
        ]
    elif "students" in schema.lower() or "courses" in schema.lower():
        examples = [
            "Show all students enrolled in Computer Science",
            "Which courses have more than 30 students?",
            "Find students with GPA above 3.5",
            "List all courses taught by Professor Johnson",
            "What is the average grade for each course?"
        ]
    else:
        # Generic examples
        examples = [
            "Show all records from the main table",
            "Count the total number of records",
            "Find the most recent entries",
            "Group data by category and count",
            "Show records that meet multiple conditions"
        ]
    
    with st.expander("💡 Example Questions"):
        st.markdown("Try these example questions:")
        for example in examples:
            if st.button(example, key=f"example_{example}", use_container_width=True):
                st.session_state.nl_example = example
                st.rerun()

def validate_schema(schema):
    """Basic validation of schema format"""
    schema_upper = schema.upper()
    return "CREATE TABLE" in schema_upper and "(" in schema and ")" in schema

def extract_sql_from_response(response):
    """Extract SQL from response if not properly formatted"""
    lines = response.split('\n')
    sql_lines = []
    in_sql = False
    
    for line in lines:
        if line.strip().startswith('SQL:'):
            in_sql = True
            continue
        elif line.strip().startswith('Explanation:') or line.strip().startswith('Assumptions:'):
            in_sql = False
        elif in_sql and line.strip():
            sql_lines.append(line)
    
    return '\n'.join(sql_lines)

# Schema storage functions
def save_user_schema(schema):
    """Save user's schema to database"""
    try:
        # Check if user already has a schema
        result = supabase.table('user_schemas').select("*").eq('user_email', st.session_state.user_email).execute()
        
        if result.data:
            # Update existing schema
            supabase.table('user_schemas').update({
                'schema_text': schema,
                'updated_at': 'now()'
            }).eq('user_email', st.session_state.user_email).execute()
        else:
            # Insert new schema
            supabase.table('user_schemas').insert({
                'user_email': st.session_state.user_email,
                'schema_text': schema
            }).execute()
        
        st.session_state.user_schema = schema
    except Exception as e:
        st.error(f"Error saving schema: {str(e)}")

def load_user_schema():
    """Load user's saved schema from database"""
    try:
        result = supabase.table('user_schemas').select("schema_text").eq('user_email', st.session_state.user_email).execute()
        if result.data:
            return result.data[0]['schema_text']
        return None
    except:
        return None

def clear_user_schema():
    """Clear user's saved schema"""
    try:
        supabase.table('user_schemas').delete().eq('user_email', st.session_state.user_email).execute()
        if 'user_schema' in st.session_state:
            del st.session_state.user_schema
    except Exception as e:
        st.error(f"Error clearing schema: {str(e)}")