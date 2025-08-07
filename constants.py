# constants.py

TASK_DESCRIPTIONS = {
    "Explain": "Get a detailed step-by-step explanation",
    "Optimize": "Improve performance and efficiency",
    "Detect Issues": "Find problems and bad practices",
    "Test": "Generate test data and expected results"
}

PROMPT_TEMPLATES = {
    "Explain": """Provide a comprehensive analysis of this SQL query.

Structure your response:
1. QUERY PURPOSE - What problem it solves
2. EXECUTION BREAKDOWN - Step-by-step processing
3. TECHNICAL ANALYSIS - Table relationships and logic
4. PERFORMANCE CONSIDERATIONS - Bottlenecks and scalability
5. ASSUMPTIONS & DEPENDENCIES

SQL Query:
{sql_query}""",

    "Detect Issues": """Analyze this query for issues.

Check for:
1. PERFORMANCE ISSUES - Inefficiencies
2. SECURITY VULNERABILITIES - Injection risks
3. MAINTAINABILITY PROBLEMS - Readability issues
4. BEST PRACTICE VIOLATIONS

Rate severity: CRITICAL, HIGH, MEDIUM, LOW

SQL Query:
{sql_query}""",

    "Optimize": """Optimize this SQL query for better performance.

Provide:
1. PERFORMANCE ANALYSIS
2. OPTIMIZATION STRATEGY
3. OPTIMIZED VERSION
4. IMPLEMENTATION NOTES
5. TRADE-OFF ANALYSIS

Original SQL Query:
{sql_query}""",

    "Test": """Create a test suite for this query.

Include:
1. TEST DATA DESIGN - Sample data with edge cases
2. EXPECTED RESULTS - Complete output
3. EDGE CASE SCENARIOS
4. VALIDATION CRITERIA
5. TEST EXECUTION PLAN

SQL Query to Test:
{sql_query}"""
}
