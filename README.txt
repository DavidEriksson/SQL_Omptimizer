SQL Optimizer AI
A professional SQL query optimization and analysis tool built with Streamlit and Supabase.

Project Structure
sql-optimizer-ai/
├── main.py                 # Main application entry point
├── config.py              # Configuration and settings
├── database.py            # Database operations and queries
├── auth.py                # Authentication module
├── utils.py               # Utility functions
├── components/
│   └── sidebar.py         # Sidebar navigation component
├── pages/
│   ├── home.py           # Home page
│   ├── optimizer.py      # SQL optimizer page
│   ├── history.py        # Query history page
│   ├── analytics.py      # Analytics dashboard (admin only)
│   └── users.py          # User management (admin only)
├── requirements.txt       # Python dependencies
└── README.md             # Project documentation
Features
SQL Query Analysis: Analyze, optimize, detect issues, and test SQL queries
User Authentication: Secure login/registration with bcrypt password hashing
Role-Based Access: Admin and standard user roles
Query History: Save, favorite, and reuse previous queries
Usage Limits: Daily query limits for standard users (5 queries/day)
Analytics Dashboard: Track usage, performance, and costs (admin only)
User Management: Admin tools for managing users and passwords
SQL Formatter: Built-in SQL formatting tool
Setup
1. Supabase Database Setup
Create these tables in your Supabase dashboard:

sql
-- Users table
CREATE TABLE users (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Query logs table
CREATE TABLE query_logs (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_email TEXT NOT NULL,
    task_type TEXT NOT NULL,
    query_length INTEGER NOT NULL,
    tokens_used INTEGER,
    success BOOLEAN NOT NULL,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Query history table
CREATE TABLE query_history (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_email TEXT NOT NULL,
    query_text TEXT NOT NULL,
    task_type TEXT NOT NULL,
    result_text TEXT,
    is_favorite BOOLEAN DEFAULT FALSE,
    query_name TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
2. Streamlit Secrets Configuration
Add these to your Streamlit Cloud secrets:

toml
OPENAI_API_KEY = "your-openai-api-key"
ADMIN_EMAILS = ["admin@example.com", "youremail@example.com"]
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_KEY = "your-anon-public-key"
3. Installation
bash
pip install -r requirements.txt
4. Running the Application
bash
streamlit run main.py
File Descriptions
Core Files
main.py: Application entry point, handles routing and main UI structure
config.py: Manages configuration, secrets, and Supabase client initialization
database.py: All database operations including user management, query logging, and analytics
auth.py: Authentication logic for login and registration
utils.py: Utility functions like SQL formatting and prompt templates
Components
components/sidebar.py: Sidebar navigation, user status, and usage tracking
Pages
pages/home.py: Dashboard with quick actions and recent activity
pages/optimizer.py: Main SQL analysis interface with OpenAI integration
pages/history.py: Query history management with search and favorites
pages/analytics.py: Admin dashboard with usage metrics and trends
pages/users.py: User management tools for admins
Key Functions
Database Operations (database.py)
add_user(): Create new user with hashed password
get_user(): Retrieve user by email
verify_password(): Verify bcrypt hashed password
log_query(): Log query usage for analytics
save_query_to_history(): Save queries for later use
get_analytics_data(): Aggregate analytics data
Authentication (auth.py)
login_page(): Render login/register interface
login_form(): Handle user login
register_form(): Handle user registration
Utilities (utils.py)
format_sql(): Format SQL with proper capitalization
get_prompt_templates(): Get OpenAI prompts for different tasks
Usage
Register/Login: Create an account or login with existing credentials
Analyze SQL: Paste SQL query and select analysis type (Explain, Optimize, Detect Issues, Test)
View History: Access previous queries, mark favorites, and reuse queries
Analytics (Admin only): View usage statistics and trends
User Management (Admin only): Manage users, reset passwords, grant admin access
Admin Features
Users listed in ADMIN_EMAILS automatically get admin privileges, which include:

Unlimited queries (no daily limit)
Access to Analytics Dashboard
User Management capabilities
View all system metrics
Security
Passwords are hashed using bcrypt
Supabase handles database security
API keys are stored in Streamlit secrets
Role-based access control for sensitive features
License
MIT License

Support
For issues or questions, please create an issue in the repository.

