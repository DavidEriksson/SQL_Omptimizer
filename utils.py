import re

def format_sql(sql_query):
    """Format SQL query with proper capitalization and spacing"""
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
    
    # Clean up spacing
    result = re.sub(r'[ \t]+', ' ', result)
    result = re.sub(r' +\n', '\n', result)
    result = re.sub(r'\n +', '\n', result)
    result = re.sub(r' ,', ',', result)
    result = re.sub(r',([a-zA-Z0-9_])', r', \1', result)
    result = re.sub(r'\( ', '(', result)
    result = re.sub(r' \)', ')', result)
    
    return result.strip()

def get_prompt_templates(sql_query, task):
    """Get the appropriate prompt template for the given task"""
    templates = {
        "Explain": f"""Provide a comprehensive analysis of this SQL query.

Structure your response:
1. QUERY PURPOSE - What problem it solves
2. EXECUTION BREAKDOWN - Step-by-step processing
3. TECHNICAL ANALYSIS - Table relationships and logic
4. PERFORMANCE CONSIDERATIONS - Bottlenecks and scalability
5. ASSUMPTIONS & DEPENDENCIES

SQL Query:
{sql_query}""",

        "Detect Issues": f"""Analyze this query for issues.

Check for:
1. PERFORMANCE ISSUES - Inefficiencies
2. SECURITY VULNERABILITIES - Injection risks
3. MAINTAINABILITY PROBLEMS - Readability issues
4. BEST PRACTICE VIOLATIONS

Rate severity: CRITICAL, HIGH, MEDIUM, LOW

SQL Query:
{sql_query}""",

        "Optimize": f"""Optimize this SQL query for better performance.

Provide:
1. PERFORMANCE ANALYSIS
2. OPTIMIZATION STRATEGY
3. OPTIMIZED VERSION
4. IMPLEMENTATION NOTES
5. TRADE-OFF ANALYSIS

Original SQL Query:
{sql_query}""",

        "Test": f"""Create a test suite for this query.

Include:
1. TEST DATA DESIGN - Sample data with edge cases
2. EXPECTED RESULTS - Complete output
3. EDGE CASE SCENARIOS
4. VALIDATION CRITERIA
5. TEST EXECUTION PLAN

SQL Query to Test:
{sql_query}"""
    }
    
    return templates.get(task, templates["Explain"])