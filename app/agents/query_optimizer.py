"""
Query Optimizer

Adds ClickHouse-specific optimization hints and suggestions to generated SQL.
"""

import re
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass


logger = logging.getLogger("agents.query_optimizer")


@dataclass
class OptimizationHint:
    """A query optimization hint"""
    hint: str
    description: str
    category: str  # 'performance', 'memory', 'stability', 'best_practice'


class QueryOptimizer:
    """
    Analyzes and optimizes ClickHouse SQL queries.

    Provides optimization hints for:
    - Partition pruning
    - Index usage
    - Memory efficiency
    - Query performance
    """

    def __init__(self):
        self.optimizations: List[OptimizationHint] = []

    def analyze_and_optimize(self, sql: str, schema: Dict[str, Any] = None) -> str:
        """
        Analyze SQL and add optimization hints.

        Args:
            sql: SQL query to analyze
            schema: Database schema (optional, for context-aware hints)

        Returns:
            Optimized SQL with hints
        """
        self.optimizations = []
        optimized = sql

        # Add ClickHouse settings for optimization
        optimized = self._add_optimization_settings(optimized)

        # Check for common anti-patterns
        optimized = self._check_anti_patterns(optimized)

        # Suggest index usage if schema provided
        if schema:
            optimized = self._suggest_index_usage(optimized, schema)

        # Check for partition key usage
        if schema:
            optimized = self._check_partition_pruning(optimized, schema)

        # Optimize JOINs
        optimized = self._optimize_joins(optimized)

        # Optimize aggregations
        optimized = self._optimize_aggregations(optimized)

        # Add FINAL modifier for ReplacingMergeTree if needed
        optimized = self._add_final_modifier(optimized, schema)

        # Optimize ORDER BY
        optimized = self._optimize_order_by(optimized)

        # Check for LIMIT optimization
        optimized = self._optimize_limit(optimized)

        logger.info(f"Applied {len(self.optimizations)} optimization hints")

        return optimized

    def _add_optimization_settings(self, sql: str) -> str:
        """Add ClickHouse SETTINGS clause for optimization"""
        if "SETTINGS" in sql.upper():
            # Already has settings, return as-is
            return sql

        # Determine if query needs optimization settings
        needs_settings = any([
            "JOIN" in sql.upper(),
            "GROUP BY" in sql.upper(),
            "ORDER BY" in sql.upper(),
            "DISTINCT" in sql.upper(),
        ])

        if not needs_settings:
            return sql

        # Add optimization settings
        settings = []

        # JOIN optimization
        if "JOIN" in sql.upper():
            settings.append("join_use_nulls = 1")
            settings.append("max_threads = 4")
            self._add_hint(
                "join_use_nulls = 1, max_threads = 4",
                "Added JOIN optimization settings for consistent NULL handling and parallelism",
                "performance"
            )

        # Aggregation optimization
        if "GROUP BY" in sql.upper():
            settings.append("max_bytes_before_external_sort = 1073741824")  # 1GB
            settings.append("max_bytes_before_external_group_by = 1073741824")  # 1GB
            self._add_hint(
                "max_bytes_before_external_sort = 1GB, max_bytes_before_external_group_by = 1GB",
                "Enabled external sort/group by for memory-efficient aggregations",
                "memory"
            )

        # ORDER BY optimization
        if "ORDER BY" in sql.upper():
            settings.append("max_block_size = 65536")
            self._add_hint(
                "max_block_size = 65536",
                "Optimized block size for ORDER BY operations",
                "performance"
            )

        # DISTINCT optimization
        if "DISTINCT" in sql.upper():
            settings.append("optimize_distinct_in_order = 1")
            self._add_hint(
                "optimize_distinct_in_order = 1",
                "Optimized DISTINCT by using ORDER BY optimization",
                "performance"
            )

        if settings:
            settings_str = ", ".join(settings)
            # Insert SETTINGS before the query terminator
            if ";" in sql:
                sql = sql.replace(";", f" SETTINGS {settings_str};")
            else:
                sql = f"{sql} SETTINGS {settings_str}"

        return sql

    def _check_anti_patterns(self, sql: str) -> str:
        """Check for common anti-patterns and suggest fixes"""
        sql_upper = sql.upper()

        # Check for SELECT *
        if re.search(r'SELECT\s+\*', sql_upper):
            self._add_hint(
                "Avoid SELECT *",
                "SELECT * can be inefficient. Specify only needed columns.",
                "best_practice"
            )

        # Check for NOT IN with NULLs
        if "NOT IN" in sql_upper and "IS NOT NULL" not in sql_upper:
            self._add_hint(
                "NOT IN with NULLs",
                "NOT IN returns no results if subquery contains NULLs. Consider using NOT EXISTS.",
                "stability"
            )

        # Check for subqueries in WHERE clause
        if re.search(r'WHERE\s+\(SELECT', sql_upper):
            self._add_hint(
                "Subquery in WHERE",
                "Subqueries in WHERE can be slow. Consider JOINs or CTEs.",
                "performance"
            )

        # Check for ORDER BY without LIMIT
        if "ORDER BY" in sql_upper and "LIMIT" not in sql_upper:
            self._add_hint(
                "ORDER BY without LIMIT",
                "ORDER BY without LIMIT can be memory-intensive. Consider adding LIMIT.",
                "memory"
            )

        # Check for large LIMIT values
        limit_match = re.search(r'LIMIT\s+(\d+)', sql_upper)
        if limit_match and int(limit_match.group(1)) > 10000:
            self._add_hint(
                f"Large LIMIT value: {limit_match.group(1)}",
                "Large LIMIT can cause performance issues. Consider pagination.",
                "performance"
            )

        # Check for OR conditions (can be slow)
        or_count = sql_upper.count(" OR ")
        if or_count > 2:
            self._add_hint(
                f"Multiple OR conditions ({or_count})",
                "Many OR conditions can be slow. Consider IN clause or array functions.",
                "performance"
            )

        # Check for LIKE without prefix
        like_matches = re.findall(r"LIKE\s+'([^%]+)%'", sql_upper)
        if like_matches:
            self._add_hint(
                "LIKE with leading wildcard",
                "LIKE 'value%' can use indexes, but LIKE '%value%' cannot. Consider full-text search.",
                "performance"
            )

        return sql

    def _suggest_index_usage(self, sql: str, schema: Dict[str, Any]) -> str:
        """Suggest index/primary key usage based on WHERE clause"""
        # Extract WHERE clause
        where_match = re.search(r'WHERE\s+(.+?)(?:\s+GROUP BY|\s+ORDER BY|\s+LIMIT|;|$)', sql, re.IGNORECASE)
        if not where_match:
            return sql

        where_clause = where_match.group(1)

        # Check for tables in query
        tables = re.findall(r'FROM\s+(\w+)|JOIN\s+(\w+)', sql, re.IGNORECASE)
        table_names = [t[0] or t[1] for t in tables if t]

        for table_name in table_names:
            if table_name not in schema.get("tables", {}):
                continue

            table_info = schema["tables"][table_name]

            # Get primary key columns
            pk_columns = [
                col["name"] for col in table_info["columns"]
                if col.get("primary_key")
            ]

            if not pk_columns:
                continue

            # Check if WHERE clause uses any PK columns
            pk_used = any(
                re.search(rf'\b{pk}\b', where_clause, re.IGNORECASE)
                for pk in pk_columns
            )

            if pk_used:
                self._add_hint(
                    f"Primary key used: {', '.join(pk_columns)}",
                    f"WHERE clause uses primary key columns for table '{table_name}'. Good for partition pruning.",
                    "performance"
                )

        return sql

    def _check_partition_pruning(self, sql: str, schema: Dict[str, Any]) -> str:
        """Check for partition key usage"""
        # Get tables and their partition keys
        tables = re.findall(r'FROM\s+(\w+)|JOIN\s+(\w+)', sql, re.IGNORECASE)
        table_names = [t[0] or t[1] for t in tables if t]

        for table_name in table_names:
            if table_name not in schema.get("tables", {}):
                continue

            table_info = schema["tables"][table_name]
            create_query = table_info.get("create_query", "")

            # Extract partition key from CREATE TABLE
            partition_match = re.search(r'PARTITION BY\s+(.+?)(?:\s+ORDER BY|\s+SETTINGS|;)', create_query, re.IGNORECASE)
            if not partition_match:
                continue

            partition_key = partition_match.group(1).strip()

            # Check if partition key is used in WHERE clause
            where_match = re.search(r'WHERE\s+(.+?)(?:\s+GROUP BY|\s+ORDER BY|\s+LIMIT|;|$)', sql, re.IGNORECASE)
            if where_match:
                where_clause = where_match.group(1)
                if re.search(rf'\b{re.escape(partition_key)}\b', where_clause, re.IGNORECASE):
                    self._add_hint(
                        f"Partition pruning active: {partition_key}",
                        f"WHERE clause filters on partition key '{partition_key}' for table '{table_name}'.",
                        "performance"
                    )
                else:
                    self._add_hint(
                        f"Missing partition filter: {partition_key}",
                        f"Consider filtering on partition key '{partition_key}' for table '{table_name}' to improve performance.",
                        "performance"
                    )

        return sql

    def _optimize_joins(self, sql: str) -> str:
        """Optimize JOIN operations"""
        # Check for JOIN without USING
        if re.search(r'JOIN\s+\w+\s+ON\s+\w+\.\w+\s*=\s*\w+\.\w+', sql, re.IGNORECASE):
            self._add_hint(
                "JOIN with ON clause",
                "Consider USING for equijoins when column names match. It's more efficient.",
                "performance"
            )

        # Check for subquery in JOIN
        if re.search(r'JOIN\s+\(SELECT', sql, re.IGNORECASE):
            self._add_hint(
                "JOIN with subquery",
                "Subqueries in JOINs can be slow. Consider CTEs or pre-aggregation.",
                "performance"
            )

        return sql

    def _optimize_aggregations(self, sql: str) -> str:
        """Optimize aggregation queries"""
        # Check for COUNT(DISTINCT)
        if "COUNT(DISTINCT" in sql.upper():
            self._add_hint(
                "COUNT(DISTINCT)",
                "COUNT(DISTINCT) can be memory-intensive. Consider uniq() or uniqExact() for large datasets.",
                "memory"
            )

        # Check for GROUP BY without LIMIT
        if "GROUP BY" in sql.upper() and "LIMIT" not in sql.upper():
            self._add_hint(
                "GROUP BY without LIMIT",
                "GROUP BY without LIMIT can be memory-intensive. Consider adding LIMIT.",
                "memory"
            )

        return sql

    def _add_final_modifier(self, sql: str, schema: Dict[str, Any]) -> str:
        """Add FINAL modifier for ReplacingMergeTree engines"""
        if not schema:
            return sql

        # Get tables in query
        tables = re.findall(r'FROM\s+(\w+)|JOIN\s+(\w+)', sql, re.IGNORECASE)
        table_names = [t[0] or t[1] for t in tables if t]

        for table_name in table_names:
            if table_name not in schema.get("tables", {}):
                continue

            table_info = schema["tables"][table_name]
            engine = table_info.get("engine", "")

            if "ReplacingMergeTree" in engine:
                if "FINAL" not in sql.upper():
                    self._add_hint(
                        f"Add FINAL modifier for {table_name}",
                        f"Table uses ReplacingMergeTree engine. Add FINAL to get deduplicated results.",
                        "stability"
                    )
                    # Add FINAL modifier
                    sql = re.sub(
                        rf'FROM\s+{table_name}\b',
                        f'FROM {table_name} FINAL',
                        sql,
                        flags=re.IGNORECASE
                    )

        return sql

    def _optimize_order_by(self, sql: str) -> str:
        """Optimize ORDER BY clause"""
        # Check for ORDER BY without LIMIT
        if "ORDER BY" in sql.upper() and "LIMIT" not in sql.upper():
            self._add_hint(
                "ORDER BY without LIMIT",
                "ORDER BY without LIMIT can cause memory issues. Add LIMIT to limit result set.",
                "memory"
            )

        return sql

    def _optimize_limit(self, sql: str) -> str:
        """Optimize LIMIT clause"""
        # Check for missing LIMIT
        if "LIMIT" not in sql.upper():
            self._add_hint(
                "Missing LIMIT clause",
                "Consider adding LIMIT to prevent large result sets.",
                "best_practice"
            )

        return sql

    def _add_hint(self, hint: str, description: str, category: str) -> None:
        """Add an optimization hint"""
        self.optimizations.append(OptimizationHint(
            hint=hint,
            description=description,
            category=category
        ))

    def get_hints(self) -> List[Dict[str, str]]:
        """Get all optimization hints"""
        return [
            {
                "hint": opt.hint,
                "description": opt.description,
                "category": opt.category
            }
            for opt in self.optimizations
        ]

    def explain_query(self, sql: str) -> Dict[str, Any]:
        """
        Generate query explanation.

        Args:
            sql: SQL query to explain

        Returns:
            Dictionary with query explanation
        """
        explanation = {
            "original_sql": sql,
            "query_type": self._detect_query_type(sql),
            "complexity": self._assess_complexity(sql),
            "estimated_rows": self._estimate_row_count(sql),
            "optimization_hints": self.get_hints(),
            "recommendations": self._generate_recommendations(sql)
        }

        return explanation

    def _detect_query_type(self, sql: str) -> str:
        """Detect query type"""
        sql_upper = sql.upper()

        if "JOIN" in sql_upper:
            return "join"
        elif "GROUP BY" in sql_upper:
            return "aggregation"
        elif "ORDER BY" in sql_upper and "LIMIT" not in sql_upper:
            return "sort"
        elif "COUNT" in sql_upper:
            return "count"
        else:
            return "simple"

    def _assess_complexity(self, sql: str) -> str:
        """Assess query complexity"""
        sql_upper = sql.upper()

        complexity_score = 0

        if "JOIN" in sql_upper:
            complexity_score += sql_upper.count("JOIN") * 2
        if "GROUP BY" in sql_upper:
            complexity_score += 2
        if "ORDER BY" in sql_upper:
            complexity_score += 1
        if "HAVING" in sql_upper:
            complexity_score += 2
        if "SUBQUERY" in sql_upper or "IN (" in sql_upper or "EXISTS" in sql_upper:
            complexity_score += 2
        if "UNION" in sql_upper:
            complexity_score += 2

        if complexity_score <= 2:
            return "low"
        elif complexity_score <= 5:
            return "medium"
        else:
            return "high"

    def _estimate_row_count(self, sql: str) -> str:
        """Estimate number of rows (very rough estimate)"""
        limit_match = re.search(r'LIMIT\s+(\d+)', sql, re.IGNORECASE)
        if limit_match:
            return f"~{limit_match.group(1)}"

        if "COUNT" in sql.upper():
            return "~1"
        elif "GROUP BY" in sql.upper():
            return "varies (depends on groups)"
        elif "LIMIT" not in sql.upper():
            return "potentially large (no LIMIT)"

        return "unknown"

    def _generate_recommendations(self, sql: str) -> List[str]:
        """Generate query recommendations"""
        recommendations = []

        hints = self.get_hints()
        for hint in hints:
            if hint["category"] in ["performance", "memory"]:
                recommendations.append(hint["description"])

        return recommendations
