"""
Query Explainer

Provides detailed explanations and analysis for SQL queries.
"""

import re
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum


logger = logging.getLogger("agents.query_explainer")


class SQLDialect(str, Enum):
    """Supported SQL dialects"""
    CLICKHOUSE = "clickhouse"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SQLITE = "sqlite"
    SQLSERVER = "sqlserver"
    ORACLE = "oracle"


@dataclass
class QueryStep:
    """A step in the query execution plan"""
    step_number: int
    operation: str
    description: str
    estimated_cost: str


@dataclass
class QueryExplanation:
    """Detailed explanation of a SQL query"""
    original_sql: str
    natural_language_query: str
    generated_sql: str
    query_type: str
    complexity: str
    steps: List[QueryStep]
    tables_accessed: List[str]
    columns_accessed: List[str]
    optimization_hints: List[str]
    potential_issues: List[str]
    recommendations: List[str]


class QueryExplainer:
    """
    Explains SQL queries in natural language.

    Supports multiple SQL dialects with dialect-specific features.
    """

    def __init__(self, dialect: SQLDialect = SQLDialect.CLICKHOUSE):
        self.dialect = dialect

    def explain(
        self,
        sql: str,
        natural_language_query: str = "",
        schema: Dict[str, Any] = None
    ) -> QueryExplanation:
        """
        Generate detailed explanation of a SQL query.

        Args:
            sql: SQL query to explain
            natural_language_query: Original natural language query
            schema: Database schema (optional, for context)

        Returns:
            Detailed query explanation
        """
        # Detect query components
        query_components = self._parse_query(sql)

        # Extract tables and columns
        tables = self._extract_tables(sql)
        columns = self._extract_columns(sql, schema)

        # Generate execution steps
        steps = self._generate_execution_steps(sql, query_components)

        # Analyze query
        query_type = self._detect_query_type(sql)
        complexity = self._assess_complexity(sql, query_components)

        # Generate hints and recommendations
        hints = self._generate_optimization_hints(sql, query_components, schema)
        issues = self._detect_potential_issues(sql, query_components, schema)
        recommendations = self._generate_recommendations(sql, query_components, hints, issues)

        return QueryExplanation(
            original_sql=sql,
            natural_language_query=natural_language_query,
            generated_sql=sql,
            query_type=query_type,
            complexity=complexity,
            steps=steps,
            tables_accessed=tables,
            columns_accessed=columns,
            optimization_hints=hints,
            potential_issues=issues,
            recommendations=recommendations
        )

    def format_explanation(self, explanation: QueryExplanation) -> str:
        """
        Format query explanation as human-readable text.

        Args:
            explanation: Query explanation to format

        Returns:
            Formatted explanation text
        """
        lines = []

        lines.append("=" * 80)
        lines.append("QUERY EXPLANATION")
        lines.append("=" * 80)
        lines.append("")

        # Original natural language query
        if explanation.natural_language_query:
            lines.append("📝 Natural Language Query:")
            lines.append(f"   {explanation.natural_language_query}")
            lines.append("")

        # Generated SQL
        lines.append("💻 Generated SQL:")
        lines.append(f"   {self._format_sql_multiline(explanation.generated_sql)}")
        lines.append("")

        # Query type and complexity
        lines.append(f"🔍 Query Type: {explanation.query_type.upper()}")
        lines.append(f"📊 Complexity: {explanation.complexity.upper()}")
        lines.append("")

        # Tables accessed
        lines.append(f"📁 Tables Accessed ({len(explanation.tables_accessed)}):")
        for table in explanation.tables_accessed:
            lines.append(f"   • {table}")
        lines.append("")

        # Execution steps
        lines.append("⚡ Execution Plan:")
        for step in explanation.steps:
            cost_indicator = "⚠️" if step.estimated_cost == "high" else "✓"
            lines.append(f"   {step.step_number}. [{cost_indicator}] {step.operation}")
            lines.append(f"      {step.description}")
        lines.append("")

        # Optimization hints
        if explanation.optimization_hints:
            lines.append(f"💡 Optimization Hints ({len(explanation.optimization_hints)}):")
            for i, hint in enumerate(explanation.optimization_hints, 1):
                lines.append(f"   {i}. {hint}")
            lines.append("")

        # Potential issues
        if explanation.potential_issues:
            lines.append(f"⚠️ Potential Issues ({len(explanation.potential_issues)}):")
            for i, issue in enumerate(explanation.potential_issues, 1):
                lines.append(f"   {i}. {issue}")
            lines.append("")

        # Recommendations
        if explanation.recommendations:
            lines.append(f"✨ Recommendations ({len(explanation.recommendations)}):")
            for i, rec in enumerate(explanation.recommendations, 1):
                lines.append(f"   {i}. {rec}")
            lines.append("")

        lines.append("=" * 80)

        return "\n".join(lines)

    def _parse_query(self, sql: str) -> Dict[str, Any]:
        """Parse SQL query into components"""
        sql_upper = sql.upper()

        components = {
            "select": [],
            "from": [],
            "joins": [],
            "where": "",
            "group_by": [],
            "having": "",
            "order_by": [],
            "limit": None,
            "distinct": "DISTINCT" in sql_upper,
            "count": "COUNT" in sql_upper,
            "sum": "SUM(" in sql_upper,
            "avg": "AVG(" in sql_upper,
            "max": "MAX(" in sql_upper,
            "min": "MIN(" in sql_upper,
        }

        # Extract SELECT clause
        select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            components["select"] = [s.strip() for s in select_match.group(1).split(",")]

        # Extract FROM clause
        from_match = re.search(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        if from_match:
            components["from"] = [from_match.group(1)]

        # Extract JOINs
        join_matches = re.findall(r'(?:INNER|LEFT|RIGHT|FULL|CROSS)?\s*JOIN\s+(\w+)', sql, re.IGNORECASE)
        components["joins"] = join_matches

        # Extract WHERE clause
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+GROUP BY|\s+HAVING|\s+ORDER BY|\s+LIMIT|;|$)', sql, re.IGNORECASE | re.DOTALL)
        if where_match:
            components["where"] = where_match.group(1).strip()

        # Extract GROUP BY
        group_match = re.search(r'GROUP BY\s+(.+?)(?:\s+HAVING|\s+ORDER BY|\s+LIMIT|;|$)', sql, re.IGNORECASE)
        if group_match:
            components["group_by"] = [g.strip() for g in group_match.group(1).split(",")]

        # Extract HAVING
        having_match = re.search(r'HAVING\s+(.+?)(?:\s+ORDER BY|\s+LIMIT|;|$)', sql, re.IGNORECASE)
        if having_match:
            components["having"] = having_match.group(1).strip()

        # Extract ORDER BY
        order_match = re.search(r'ORDER BY\s+(.+?)(?:\s+LIMIT|;|$)', sql, re.IGNORECASE)
        if order_match:
            components["order_by"] = [o.strip() for o in order_match.group(1).split(",")]

        # Extract LIMIT
        limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
        if limit_match:
            components["limit"] = int(limit_match.group(1))

        return components

    def _extract_tables(self, sql: str) -> List[str]:
        """Extract table names from SQL query"""
        tables = set()

        # Extract FROM tables
        from_matches = re.findall(r'FROM\s+(\w+)', sql, re.IGNORECASE)
        tables.update(from_matches)

        # Extract JOIN tables
        join_matches = re.findall(r'JOIN\s+(\w+)', sql, re.IGNORECASE)
        tables.update(join_matches)

        return sorted(list(tables))

    def _extract_columns(self, sql: str, schema: Dict[str, Any] = None) -> List[str]:
        """Extract column names from SQL query"""
        columns = set()

        # Extract columns from SELECT clause
        select_match = re.search(r'SELECT\s+(.+?)\s+FROM', sql, re.IGNORECASE | re.DOTALL)
        if select_match:
            select_clause = select_match.group(1)
            # Remove DISTINCT and functions
            select_clause = re.sub(r'DISTINCT\s+', '', select_clause, flags=re.IGNORECASE)
            select_clause = re.sub(r'\w+\(', '', select_clause)  # Remove function names

            # Extract column names
            for col in select_clause.split(","):
                col = col.strip()
                if re.match(r'^\w+$', col):
                    columns.add(col)
                else:
                    # Handle aliases (e.g., col AS alias)
                    alias_match = re.match(r'(\w+)\s+AS\s+\w+', col, re.IGNORECASE)
                    if alias_match:
                        columns.add(alias_match.group(1))

        # Extract columns from WHERE clause
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+GROUP BY|\s+HAVING|\s+ORDER BY|\s+LIMIT|;|$)', sql, re.IGNORECASE)
        if where_match:
            where_clause = where_match.group(1)
            # Extract column references (simplified)
            col_matches = re.findall(r'\b(\w+)\s*[=<>!]', where_clause)
            columns.update(col_matches)

        return sorted(list(columns))

    def _generate_execution_steps(self, sql: str, components: Dict[str, Any]) -> List[QueryStep]:
        """Generate execution steps based on query components"""
        steps = []
        step_num = 1

        # Step 1: FROM - scan tables
        for table in components["from"]:
            steps.append(QueryStep(
                step_number=step_num,
                operation=f"SCAN TABLE {table}",
                description=f"Read all data from table '{table}'",
                estimated_cost="medium"
            ))
            step_num += 1

        # Step 2: JOINs
        for join in components["joins"]:
            steps.append(QueryStep(
                step_number=step_num,
                operation=f"JOIN {join}",
                description=f"Combine data from joined table '{join}'",
                estimated_cost="high"
            ))
            step_num += 1

        # Step 3: WHERE filter
        if components["where"]:
            steps.append(QueryStep(
                step_number=step_num,
                operation="FILTER (WHERE)",
                description=f"Filter rows based on conditions: {components['where'][:50]}...",
                estimated_cost="low" if components["joins"] else "medium"
            ))
            step_num += 1

        # Step 4: GROUP BY aggregation
        if components["group_by"]:
            steps.append(QueryStep(
                step_number=step_num,
                operation="AGGREGATE (GROUP BY)",
                description=f"Group rows by {', '.join(components['group_by'])} and compute aggregates",
                estimated_cost="high"
            ))
            step_num += 1

        # Step 5: HAVING filter
        if components["having"]:
            steps.append(QueryStep(
                step_number=step_num,
                operation="FILTER (HAVING)",
                description=f"Filter aggregated groups based on conditions: {components['having'][:50]}...",
                estimated_cost="low"
            ))
            step_num += 1

        # Step 6: ORDER BY sort
        if components["order_by"]:
            steps.append(QueryStep(
                step_number=step_num,
                operation="SORT (ORDER BY)",
                description=f"Sort results by {', '.join(components['order_by'])}",
                estimated_cost="high"
            ))
            step_num += 1

        # Step 7: LIMIT
        if components["limit"]:
            steps.append(QueryStep(
                step_number=step_num,
                operation=f"LIMIT {components['limit']}",
                description=f"Return at most {components['limit']} rows",
                estimated_cost="low"
            ))

        return steps

    def _detect_query_type(self, sql: str) -> str:
        """Detect query type"""
        sql_upper = sql.upper()

        if "JOIN" in sql_upper:
            return "join_query"
        elif "GROUP BY" in sql_upper:
            return "aggregation"
        elif "COUNT" in sql_upper or "SUM" in sql_upper:
            return "aggregation"
        elif "ORDER BY" in sql_upper:
            return "sort"
        else:
            return "simple_select"

    def _assess_complexity(self, sql: str, components: Dict[str, Any]) -> str:
        """Assess query complexity"""
        complexity_score = 0

        if components["joins"]:
            complexity_score += len(components["joins"]) * 2
        if components["group_by"]:
            complexity_score += 2
        if components["having"]:
            complexity_score += 2
        if components["order_by"]:
            complexity_score += 1
        if "JOIN" in sql.upper():
            complexity_score += 1
        if "SUBQUERY" in sql.upper() or "IN (" in sql.upper():
            complexity_score += 2
        if components["where"] and "AND" in components["where"].upper():
            complexity_score += 1

        if complexity_score <= 2:
            return "low"
        elif complexity_score <= 5:
            return "medium"
        else:
            return "high"

    def _generate_optimization_hints(
        self,
        sql: str,
        components: Dict[str, Any],
        schema: Dict[str, Any] = None
    ) -> List[str]:
        """Generate optimization hints"""
        hints = []

        # Check for missing LIMIT
        if components["limit"] is None:
            hints.append("Consider adding LIMIT to prevent large result sets")

        # Check for ORDER BY without LIMIT
        if components["order_by"] and components["limit"] is None:
            hints.append("ORDER BY without LIMIT can cause memory issues")

        # Check for COUNT(DISTINCT)
        if "COUNT(DISTINCT" in sql.upper():
            hints.append("For large datasets, consider uniq() instead of COUNT(DISTINCT)")

        # Check for SELECT *
        if re.search(r'SELECT\s+\*', sql):
            hints.append("Avoid SELECT * - specify only needed columns")

        # Check for JOINs without USING
        if components["joins"]:
            hints.append("Consider USING clause for equijoins when column names match")

        # Check for subqueries in WHERE
        if re.search(r'WHERE\s+\(SELECT', sql, re.IGNORECASE):
            hints.append("Subqueries in WHERE can be slow - consider JOINs")

        return hints

    def _detect_potential_issues(
        self,
        sql: str,
        components: Dict[str, Any],
        schema: Dict[str, Any] = None
    ) -> List[str]:
        """Detect potential issues in query"""
        issues = []

        # Check for SELECT *
        if re.search(r'SELECT\s+\*', sql):
            issues.append("SELECT * can return unnecessary columns and impact performance")

        # Check for NOT IN with NULLs
        if "NOT IN" in sql.upper():
            issues.append("NOT IN returns no results if subquery contains NULL values")

        # Check for large LIMIT
        if components["limit"] and components["limit"] > 10000:
            issues.append(f"Large LIMIT ({components['limit']}) may cause performance issues")

        # Check for many JOINs
        if len(components["joins"]) > 3:
            issues.append(f"Multiple JOINs ({len(components['joins'])}) can be slow")

        # Check for complex WHERE conditions
        if components["where"]:
            or_count = components["where"].upper().count(" OR ")
            if or_count > 3:
                issues.append(f"Multiple OR conditions ({or_count}) can impact performance")

        return issues

    def _generate_recommendations(
        self,
        sql: str,
        components: Dict[str, Any],
        hints: List[str],
        issues: List[str]
    ) -> List[str]:
        """Generate recommendations"""
        recommendations = []

        # Prioritize hints
        if issues:
            recommendations.extend(issues)
        if hints:
            recommendations.extend(hints[:3])  # Top 3 hints

        # Add dialect-specific recommendations
        if self.dialect == SQLDialect.CLICKHOUSE:
            if components["group_by"]:
                recommendations.append("Consider using max_bytes_before_external_group_by for large aggregations")
            if components["order_by"]:
                recommendations.append("Consider using max_block_size for ORDER BY optimization")

        # Add general recommendations
        if components["joins"]:
            recommendations.append("Ensure join columns are indexed")
        if components["limit"] is None:
            recommendations.append("Add LIMIT clause to control result set size")

        return recommendations

    def _format_sql_multiline(self, sql: str) -> str:
        """Format SQL query across multiple lines for readability"""
        # Simple formatting - add line breaks after major clauses
        sql = re.sub(r'\b(FROM|WHERE|GROUP BY|HAVING|ORDER BY|LIMIT|JOIN)\b', r'\n\1', sql)
        # Remove leading newline
        sql = sql.lstrip('\n')
        # Indent continuation lines
        lines = sql.split('\n')
        for i in range(1, len(lines)):
            lines[i] = '   ' + lines[i]
        return '\n'.join(lines)


def create_query_explainer(dialect: SQLDialect = SQLDialect.CLICKHOUSE) -> QueryExplainer:
    """Factory function to create QueryExplainer"""
    return QueryExplainer(dialect=dialect)
