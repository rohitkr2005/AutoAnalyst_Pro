"""
AutoAnalyst Pro - Enterprise Relational Data Modeler & DAX Query Engine
Enables multi-file/multi-sheet ingestion, automated foreign key schema discovery,
relational star/snowflake modeling, and DAX (Data Analysis Expressions) evaluation.
"""

import re
import io
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple, Union


def _clean_col_name(c: Any) -> str:
    """Sanitizes column name for consistent schema referencing."""
    return str(c).strip()


class DataModel:
    """
    In-memory Relational Data Model managing multiple tables,
    inter-table relationships, and DAX calculations.
    """

    def __init__(self):
        self.tables: Dict[str, pd.DataFrame] = {}
        self.relationships: List[Dict[str, Any]] = []
        self.measures: Dict[str, str] = {}  # measure_name -> dax_expression

    def add_table(self, name: str, df: pd.DataFrame):
        """Registers a named table in the data model."""
        clean_df = df.copy()
        clean_df.columns = [_clean_col_name(c) for c in clean_df.columns]
        self.tables[name] = clean_df

    def remove_table(self, name: str):
        """Removes a table and any associated relationships."""
        if name in self.tables:
            del self.tables[name]
        self.relationships = [
            r for r in self.relationships 
            if r["from_table"] != name and r["to_table"] != name
        ]

    def clear(self):
        """Resets the model."""
        self.tables.clear()
        self.relationships.clear()
        self.measures.clear()

    def detect_relationships(self) -> List[Dict[str, Any]]:
        """
        Heuristic scan across all loaded tables to discover potential
        primary-foreign key links (e.g. Orders.customer_id -> Customers.id).
        Restricts candidate columns to key/ID patterns and verifies high cardinality in lookup table.
        """
        discovered = []
        table_names = list(self.tables.keys())
        if len(table_names) < 2:
            return discovered

        KEY_PATTERNS = ('id', 'code', 'key', 'no', 'num', 'number', 'pk', 'fk', 'sku', 'upc')

        def _is_key_candidate(c_name: str) -> bool:
            clean = c_name.lower().replace("_", "").replace("-", "")
            return any(clean.endswith(k) or clean == k or clean.startswith(k) for k in KEY_PATTERNS)

        for i in range(len(table_names)):
            for j in range(len(table_names)):
                if i == j:
                    continue
                t1, t2 = table_names[i], table_names[j]
                df1, df2 = self.tables[t1], self.tables[t2]

                for col1 in df1.columns:
                    if not _is_key_candidate(col1):
                        continue
                    c1_clean = col1.lower().replace("_", "").replace("-", "")
                    
                    for col2 in df2.columns:
                        if not _is_key_candidate(col2):
                            continue
                        c2_clean = col2.lower().replace("_", "").replace("-", "")
                        
                        t2_stem = re.sub(r'(?:ies|s)$', '', t2.lower())
                        t1_stem = re.sub(r'(?:ies|s)$', '', t1.lower())
                        is_match = False
                        if c1_clean == c2_clean:
                            is_match = True
                        elif c2_clean in ["id", f"{t2_stem}id", "key", f"{t2_stem}key"] and (t2_stem in c1_clean):
                            is_match = True
                        elif c1_clean in ["id", f"{t1_stem}id", "key", f"{t1_stem}key"] and (t1_stem in c2_clean):
                            is_match = True
                        elif (t2_stem and t2_stem in c1_clean) and (c2_clean == "id" or c2_clean in c1_clean):
                            is_match = True

                        if is_match:
                            try:
                                # Sample max 2000 non-null values for fast intersection
                                s1 = df1[col1].dropna().head(2000).astype(str).str.strip().unique()
                                s2_series = df2[col2].dropna().head(2000)
                                s2 = s2_series.astype(str).str.strip().unique()
                                
                                # In table 2 (lookup table), verify key has reasonably high uniqueness to prevent Cartesian explosions
                                if len(s2_series) > 0:
                                    uniqueness_t2 = len(s2) / len(s2_series)
                                    if uniqueness_t2 < 0.4:
                                        # Not a true primary key in t2, skip
                                        continue

                                if len(s1) > 0 and len(s2) > 0:
                                    overlap = len(set(s1).intersection(set(s2)))
                                    ratio = overlap / min(len(s1), len(s2))
                                    if ratio >= 0.15:  # Valid key overlap
                                        is_unique_in_t2 = (len(s2) == len(s2_series))
                                        cardinality = "many_to_one" if is_unique_in_t2 else "many_to_many"
                                        
                                        rel_entry = {
                                            "from_table": t1,
                                            "from_col": col1,
                                            "to_table": t2,
                                            "to_col": col2,
                                            "cardinality": cardinality,
                                            "overlap_ratio": round(float(ratio), 2)
                                        }
                                        if not any(
                                            (r["from_table"] == t2 and r["to_table"] == t1 and r["from_col"] == col2 and r["to_col"] == col1)
                                            or (r["from_table"] == t1 and r["to_table"] == t2 and r["from_col"] == col1 and r["to_col"] == col2)
                                            for r in self.relationships + discovered
                                        ):
                                            discovered.append(rel_entry)
                            except Exception:
                                pass

        for d in discovered:
            if not any(
                r["from_table"] == d["from_table"] and r["from_col"] == d["from_col"] and
                r["to_table"] == d["to_table"] and r["to_col"] == d["to_col"]
                for r in self.relationships
            ):
                self.relationships.append(d)

        return discovered

    def add_relationship(self, from_table: str, from_col: str, to_table: str, to_col: str, cardinality: str = "many_to_one") -> bool:
        """Adds or updates a foreign key relationship."""
        if from_table not in self.tables or to_table not in self.tables:
            return False
        if from_col not in self.tables[from_table].columns or to_col not in self.tables[to_table].columns:
            return False

        self.relationships = [
            r for r in self.relationships
            if not (r["from_table"] == from_table and r["from_col"] == from_col and r["to_table"] == to_table and r["to_col"] == to_col)
        ]
        self.relationships.append({
            "from_table": from_table,
            "from_col": from_col,
            "to_table": to_table,
            "to_col": to_col,
            "cardinality": cardinality
        })
        return True

    def remove_relationship(self, from_table: str, from_col: str, to_table: str, to_col: str):
        """Deletes a relationship link."""
        self.relationships = [
            r for r in self.relationships
            if not (r["from_table"] == from_table and r["from_col"] == from_col and r["to_table"] == to_table and r["to_col"] == to_col)
        ]

    def get_schema_summary(self) -> Dict[str, Any]:
        """Provides full metadata of all tables, schema columns, types, and links."""
        tables_meta = []
        for name, df in self.tables.items():
            cols = []
            for col in df.columns:
                dtype_str = str(df[col].dtype)
                if "int" in dtype_str:
                    col_type = "INTEGER"
                elif "float" in dtype_str:
                    col_type = "DECIMAL"
                elif "datetime" in dtype_str:
                    col_type = "DATETIME"
                elif "bool" in dtype_str:
                    col_type = "BOOLEAN"
                else:
                    col_type = "STRING"

                is_fk = any(r["from_table"] == name and r["from_col"] == col for r in self.relationships)
                is_pk = any(r["to_table"] == name and r["to_col"] == col for r in self.relationships)

                cols.append({
                    "name": col,
                    "type": col_type,
                    "is_fk": is_fk,
                    "is_pk": is_pk,
                    "null_count": int(df[col].isna().sum())
                })

            clean_sample = df.head(5).copy()
            for col in clean_sample.columns:
                clean_sample[col] = clean_sample[col].astype(str).replace({"nan": "", "None": "", "<NA>": "", "NaT": ""})
            sample_rows = clean_sample.to_dict(orient="records")

            tables_meta.append({
                "name": name,
                "rows": len(df),
                "cols": len(df.columns),
                "columns": cols,
                "sample": sample_rows
            })

        return {
            "tables": tables_meta,
            "relationships": self.relationships,
            "total_tables": len(self.tables),
            "measures_count": len(self.measures)
        }

    def build_joined_dataframe(self, base_table: Optional[str] = None) -> pd.DataFrame:
        """
        Executes relational joins across all connected tables starting
        from the primary base table (or table with highest row count).
        Deduplicates lookup tables and normalizes keys to prevent Cartesian explosions.
        """
        if not self.tables:
            return pd.DataFrame()

        if not base_table or base_table not in self.tables:
            base_table = max(self.tables.keys(), key=lambda t: len(self.tables[t]))

        joined = self.tables[base_table].copy()
        visited_tables = {base_table}

        max_hops = len(self.tables) + 1
        for _ in range(max_hops):
            progress_made = False
            for rel in self.relationships:
                from_t = rel["from_table"]
                to_t = rel["to_table"]

                if from_t in visited_tables and to_t not in visited_tables:
                    right_df = self.tables[to_t].copy()
                    rename_map = {
                        c: f"{to_t}_{c}" for c in right_df.columns if c != rel["to_col"] and c in joined.columns
                    }
                    right_df = right_df.rename(columns=rename_map)
                    right_key = rename_map.get(rel["to_col"], rel["to_col"])

                    # Prevent Cartesian explosion: deduplicate lookup table on join key
                    right_df = right_df.drop_duplicates(subset=[right_key])

                    try:
                        temp_k_left = f"__temp_k_{rel['from_col']}"
                        temp_k_right = f"__temp_k_{right_key}"
                        joined[temp_k_left] = joined[rel["from_col"]].astype(str).str.strip()
                        right_df[temp_k_right] = right_df[right_key].astype(str).str.strip()

                        # If right_key is in joined, drop it from right_df to prevent Pandas _x and _y suffixes
                        if right_key in joined.columns:
                            right_df = right_df.drop(columns=[right_key], errors="ignore")

                        joined = pd.merge(
                            joined,
                            right_df,
                            how="left",
                            left_on=temp_k_left,
                            right_on=temp_k_right
                        )
                        joined = joined.drop(columns=[temp_k_left, temp_k_right], errors="ignore")
                        visited_tables.add(to_t)
                        progress_made = True
                    except Exception as e:
                        print(f"[Join Error] {from_t} -> {to_t}: {e}", flush=True)

                elif to_t in visited_tables and from_t not in visited_tables:
                    left_df = self.tables[from_t].copy()
                    rename_map = {
                        c: f"{from_t}_{c}" for c in left_df.columns if c != rel["from_col"] and c in joined.columns
                    }
                    left_df = left_df.rename(columns=rename_map)
                    left_key = rename_map.get(rel["from_col"], rel["from_col"])

                    # Prevent Cartesian explosion: deduplicate lookup table on join key
                    left_df = left_df.drop_duplicates(subset=[left_key])

                    try:
                        temp_k_left = f"__temp_k_{rel['to_col']}"
                        temp_k_right = f"__temp_k_{left_key}"
                        joined[temp_k_left] = joined[rel["to_col"]].astype(str).str.strip()
                        left_df[temp_k_right] = left_df[left_key].astype(str).str.strip()

                        # If left_key is in joined, drop it from left_df to prevent Pandas _x and _y suffixes
                        if left_key in joined.columns:
                            left_df = left_df.drop(columns=[left_key], errors="ignore")

                        joined = pd.merge(
                            joined,
                            left_df,
                            how="left",
                            left_on=temp_k_left,
                            right_on=temp_k_right
                        )
                        joined = joined.drop(columns=[temp_k_left, temp_k_right], errors="ignore")
                        visited_tables.add(from_t)
                        progress_made = True
                    except Exception as e:
                        print(f"[Join Error] {to_t} -> {from_t}: {e}", flush=True)

            if not progress_made:
                break

        return joined


# ============================================================
# DAX (DATA ANALYSIS EXPRESSIONS) PARSER & EVALUATOR
# ============================================================

def parse_table_column(token: str) -> Tuple[Optional[str], str]:
    """
    Parses Table[Column] or [Column] into (table_name, column_name).
    """
    m = re.match(r'^(?:([a-zA-Z0-9_\s]+)\[([a-zA-Z0-9_\s]+)\]|\[([a-zA-Z0-9_\s]+)\]|([a-zA-Z0-9_\s]+))$', token.strip())
    if not m:
        return None, token.strip()
    if m.group(1) and m.group(2):
        return m.group(1).strip(), m.group(2).strip()
    if m.group(3):
        return None, m.group(3).strip()
    return None, m.group(4).strip()


class DaxEngine:
    """
    Executes DAX (Data Analysis Expressions) queries and calculations
    against an active DataModel.
    """

    def __init__(self, model: DataModel):
        self.model = model

    def resolve_column(self, table_name: Optional[str], col_name: str, joined_df: Optional[pd.DataFrame] = None) -> Tuple[pd.Series, str]:
        """Finds the column Series across the model."""
        if table_name and table_name in self.model.tables:
            df = self.model.tables[table_name]
            if col_name in df.columns:
                return df[col_name], table_name

        if joined_df is not None:
            if col_name in joined_df.columns:
                return joined_df[col_name], "Joined"
            for c in joined_df.columns:
                if c.endswith(f"_{col_name}") or c.lower() == col_name.lower():
                    return joined_df[c], "Joined"

        for t_name, df in self.model.tables.items():
            if col_name in df.columns:
                return df[col_name], t_name

        raise ValueError(f"Column '{col_name}' could not be resolved in the data model.")

    def evaluate_aggregation(self, func_name: str, col_arg: str, df_context: Optional[pd.DataFrame] = None) -> float:
        """Evaluates basic aggregate functions: SUM, AVERAGE, MIN, MAX, COUNT, DISTINCTCOUNT."""
        t_name, c_name = parse_table_column(col_arg)
        
        if df_context is not None:
            if c_name in df_context.columns:
                series = df_context[c_name]
            else:
                series, _ = self.resolve_column(t_name, c_name, df_context)
        else:
            series, _ = self.resolve_column(t_name, c_name)

        num_series = pd.to_numeric(series, errors="coerce").dropna()
        f = func_name.upper()

        if f == "SUM":
            return float(num_series.sum())
        elif f in ["AVERAGE", "AVG"]:
            return float(num_series.mean()) if len(num_series) > 0 else 0.0
        elif f == "MIN":
            return float(num_series.min()) if len(num_series) > 0 else 0.0
        elif f == "MAX":
            return float(num_series.max()) if len(num_series) > 0 else 0.0
        elif f == "COUNT":
            return float(series.count())
        elif f in ["DISTINCTCOUNT", "DISTINCT_COUNT"]:
            return float(series.nunique())
        elif f == "COUNTROWS":
            if t_name and t_name in self.model.tables:
                return float(len(self.model.tables[t_name]))
            return float(len(df_context)) if df_context is not None else 0.0

        raise ValueError(f"Unsupported DAX aggregate function: '{func_name}'")

    def evaluate_scalar_dax(self, expression: str, df_context: Optional[pd.DataFrame] = None) -> Union[float, int, str]:
        """
        Evaluates scalar DAX formulas like:
          SUM(Orders[Sales])
          DIVIDE(SUM(Orders[Profit]), SUM(Orders[Sales]), 0)
          CALCULATE(SUM(Orders[Sales]), Customers[Country] = "Germany")
        """
        expr = expression.strip()

        # 1. DIVIDE(num, den, alt)
        divide_match = re.match(r'^DIVIDE\s*\((.+?),\s*(.+?)(?:,\s*(.+?))?\)$', expr, re.IGNORECASE)
        if divide_match:
            num_expr = divide_match.group(1).strip()
            den_expr = divide_match.group(2).strip()
            alt_expr = divide_match.group(3)
            alt_val = float(alt_expr.strip()) if alt_expr else 0.0

            numerator = self.evaluate_scalar_dax(num_expr, df_context)
            denominator = self.evaluate_scalar_dax(den_expr, df_context)

            if abs(float(denominator)) < 1e-12:
                return alt_val
            return float(numerator) / float(denominator)

        # 2. CALCULATE(Expression, Filter1, ...)
        calc_match = re.match(r'^CALCULATE\s*\((.+?),\s*(.+?)\)$', expr, re.IGNORECASE)
        if calc_match:
            base_expr = calc_match.group(1).strip()
            filter_expr = calc_match.group(2).strip()

            joined = self.model.build_joined_dataframe()
            filtered_df = self._apply_dax_filter(joined, filter_expr)
            return self.evaluate_scalar_dax(base_expr, filtered_df)

        # 3. COUNTROWS(Table)
        countrows_match = re.match(r'^COUNTROWS\s*\((.+?)\)$', expr, re.IGNORECASE)
        if countrows_match:
            t = countrows_match.group(1).strip()
            if df_context is not None and (t == "Model" or t not in self.model.tables):
                return len(df_context)
            if t in self.model.tables:
                return len(self.model.tables[t])
            return 0

        # 4. Standard Aggregates
        agg_match = re.match(r'^(SUM|AVERAGE|AVG|MIN|MAX|COUNT|DISTINCTCOUNT)\s*\((.+?)\)$', expr, re.IGNORECASE)
        if agg_match:
            func = agg_match.group(1)
            arg = agg_match.group(2).strip()
            return self.evaluate_aggregation(func, arg, df_context)

        # 5. Arithmetic operations
        for op in ["+", "-", "*", "/"]:
            parts = expr.split(op, 1)
            if len(parts) == 2 and not expr.startswith(f"{op}"):
                left_v = self.evaluate_scalar_dax(parts[0].strip(), df_context)
                right_v = self.evaluate_scalar_dax(parts[1].strip(), df_context)
                if op == "+":
                    return float(left_v) + float(right_v)
                elif op == "-":
                    return float(left_v) - float(right_v)
                elif op == "*":
                    return float(left_v) * float(right_v)
                elif op == "/":
                    return float(left_v) / (float(right_v) + 1e-12)

        try:
            return float(expr)
        except ValueError:
            return expr

    def _apply_dax_filter(self, df: pd.DataFrame, filter_expr: str) -> pd.DataFrame:
        """Applies DAX filter predicates like Table[Col] = 'Value' or Col > 100."""
        m = re.match(r'^(?:[a-zA-Z0-9_\s]+\[)?([a-zA-Z0-9_\s]+)\]?\s*(=|!=|<>|>|<|>=|<=|IN)\s*(.+)$', filter_expr.strip(), re.IGNORECASE)
        if not m:
            return df

        col, op, val_str = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()

        target_col = None
        if col in df.columns:
            target_col = col
        else:
            for c in df.columns:
                if c.endswith(f"_{col}") or c.lower() == col.lower():
                    target_col = c
                    break

        if not target_col:
            return df

        clean_val = val_str.strip('"\'')
        if op in ["=", "=="]:
            return df[df[target_col].astype(str).str.lower() == clean_val.lower()]
        elif op in ["!=", "<>"]:
            return df[df[target_col].astype(str).str.lower() != clean_val.lower()]
        elif op == ">":
            return df[pd.to_numeric(df[target_col], errors="coerce") > float(clean_val)]
        elif op == "<":
            return df[pd.to_numeric(df[target_col], errors="coerce") < float(clean_val)]
        elif op == ">=":
            return df[pd.to_numeric(df[target_col], errors="coerce") >= float(clean_val)]
        elif op == "<=":
            return df[pd.to_numeric(df[target_col], errors="coerce") <= float(clean_val)]
        elif op.upper() == "IN":
            items = [item.strip().strip('"\'').lower() for item in re.findall(r'[^,\(\)]+', val_str)]
            return df[df[target_col].astype(str).str.lower().isin(items)]

        return df

    def evaluate_summarize(self, query: str) -> Dict[str, Any]:
        """
        Evaluates Power BI-style DAX table queries:
          SUMMARIZE(Orders, Customers[Region], "Total Revenue", SUM(Orders[Sales]), "Profit Margin", DIVIDE(SUM(Orders[Profit]), SUM(Orders[Sales])))
        """
        m = re.match(r'^(?:EVALUATE\s+)?SUMMARIZE\s*\((.+)\)$', query.strip(), re.IGNORECASE | re.DOTALL)
        if not m:
            raise ValueError("Query must start with SUMMARIZE(...) or EVALUATE SUMMARIZE(...)")

        args_str = m.group(1).strip()
        tokens = []
        depth = 0
        curr = []
        for ch in args_str:
            if ch == '(':
                depth += 1
            elif ch == ')':
                depth -= 1
            if ch == ',' and depth == 0:
                tokens.append("".join(curr).strip())
                curr = []
            else:
                curr.append(ch)
        if curr:
            tokens.append("".join(curr).strip())

        if len(tokens) < 2:
            raise ValueError("SUMMARIZE requires at least a base Table and one GroupBy column.")

        base_table = tokens[0].strip()
        group_by_token = tokens[1].strip()
        g_tbl, group_col = parse_table_column(group_by_token)

        measures = []
        idx = 2
        while idx < len(tokens):
            m_name = tokens[idx].strip().strip('"\'')
            if idx + 1 < len(tokens):
                m_expr = tokens[idx + 1].strip()
                measures.append((m_name, m_expr))
                idx += 2
            else:
                break

        if not measures:
            measures.append(("Count", f"COUNTROWS({base_table})"))

        joined = self.model.build_joined_dataframe(base_table if base_table in self.model.tables else None)
        if joined.empty:
            raise ValueError("Data model is empty or no valid records found.")

        resolved_group_col = None
        resolved_group_col = None
        if group_col in joined.columns:
            resolved_group_col = group_col
        else:
            for c in joined.columns:
                if (
                    c == f"{group_col}_x" or c == f"{group_col}_y" or
                    c.endswith(f"_{group_col}") or c.lower() == group_col.lower() or
                    c.lower() == f"{group_col.lower()}_x" or c.lower() == f"{group_col.lower()}_y" or
                    c.lower().endswith(f"_{group_col.lower()}")
                ):
                    resolved_group_col = c
                    break

        if not resolved_group_col:
            raise ValueError(f"Group dimension '{group_col}' not found in joined model.")

        grouped = joined.groupby(resolved_group_col)
        result_rows = []

        for group_val, grp_df in grouped:
            row = {group_col: str(group_val)}
            for m_name, m_expr in measures:
                val = self.evaluate_scalar_dax(m_expr, grp_df)
                row[m_name] = round(float(val), 2) if isinstance(val, (int, float, np.number)) else val
            result_rows.append(row)

        res_df = pd.DataFrame(result_rows)
        primary_measure = measures[0][0]
        if not res_df.empty and primary_measure in res_df.columns:
            res_df = res_df.sort_values(by=primary_measure, ascending=False).head(20)

        def _to_float(v):
            try:
                if v is None or pd.isna(v):
                    return 0.0
                return round(float(v), 2)
            except Exception:
                return 0.0

        labels = [str(x) for x in res_df[group_col].tolist()] if (not res_df.empty and group_col in res_df.columns) else []
        values = [_to_float(v) for v in res_df[primary_measure].tolist()] if (not res_df.empty and primary_measure in res_df.columns) else []

        palettes = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#3b82f6', '#14b8a6']
        chart_type = "doughnut" if len(labels) <= 6 else "bar"

        return {
            "status": "success",
            "type": "table",
            "query": query,
            "columns": list(res_df.columns),
            "rows": res_df.to_dict(orient="records"),
            "total_rows": len(res_df),
            "chart": {
                "type": chart_type,
                "title": f"{primary_measure} by {group_col}",
                "labels": labels,
                "datasets": [{
                    "label": primary_measure,
                    "data": values,
                    "backgroundColor": palettes[:len(labels)],
                    "borderColor": palettes[:len(labels)],
                    "borderWidth": 1.5
                }]
            }
        }

    def _find_column_and_table(self, query_text: str) -> Tuple[Optional[str], Optional[str]]:
        """Finds the best matching column name and table name from text tokens, prioritizing descriptive columns."""
        q_tokens = query_text.lower().split()
        candidates = []
        for t_name, df in self.model.tables.items():
            for col in df.columns:
                c_clean = col.lower().replace("_", "")
                is_id = any(c_clean.endswith(k) or c_clean == k for k in ['id', 'key', 'code', 'pk', 'fk'])
                for tok in q_tokens:
                    tok_clean = tok.replace("_", "")
                    if tok_clean == c_clean:
                        candidates.append((0 if not is_id else 2, col, t_name))
                    elif (len(tok_clean) >= 3 and tok_clean in c_clean) or (len(c_clean) >= 3 and c_clean in tok_clean):
                        candidates.append((1 if not is_id else 3, col, t_name))
        if candidates:
            candidates.sort(key=lambda x: x[0])
            return candidates[0][1], candidates[0][2]
        return None, None

    def generate_automated_measures(self) -> List[Dict[str, Any]]:
        """
        Autonomously analyzes table schemas, foreign key links, and data types
        to synthesize high-value executive DAX measures and dimensional summaries.
        """
        if not self.model.tables:
            return []

        auto_measures = []

        # 1. Identify primary Fact table (highest row count or most foreign keys)
        fact_candidates = sorted(
            self.model.tables.keys(),
            key=lambda t: (sum(1 for r in self.model.relationships if r["from_table"] == t), len(self.model.tables[t])),
            reverse=True
        )
        fact_table = fact_candidates[0]
        fact_df = self.model.tables[fact_table]

        # 2. Identify numeric measures in Fact table
        num_cols = fact_df.select_dtypes(include=[np.number]).columns.tolist()
        metric_cols = [c for c in num_cols if not re.search(r'(?:_id|id$|^id$|code|key|index)', c.lower())]
        if not metric_cols and num_cols:
            metric_cols = num_cols

        # 3. Base Fact Aggregations (Total Revenue, Total Sales, Units, Volume)
        for col in metric_cols[:4]:
            clean_name = col.replace("_", " ").title()
            sum_expr = f"SUM({fact_table}[{col}])"
            try:
                val = self.evaluate_scalar_dax(sum_expr)
                is_curr = any(k in col.lower() for k in ["sales", "revenue", "profit", "price", "amount", "cost"])
                formatted_val = f"${val:,.2f}" if is_curr else f"{val:,.2f}"
                auto_measures.append({
                    "id": f"sum_{col}",
                    "name": f"Total {clean_name}",
                    "title": f"Total {clean_name}",
                    "category": "Core Aggregation",
                    "expression": sum_expr,
                    "dax": sum_expr,
                    "type": "scalar",
                    "value": val,
                    "formatted": formatted_val,
                    "description": f"Calculates total sum of {clean_name} across {fact_table}."
                })
            except Exception:
                pass

            avg_expr = f"AVERAGE({fact_table}[{col}])"
            try:
                val = self.evaluate_scalar_dax(avg_expr)
                is_curr = any(k in col.lower() for k in ["sales", "revenue", "profit", "price", "amount", "cost"])
                formatted_val = f"${val:,.2f}" if is_curr else f"{val:,.2f}"
                auto_measures.append({
                    "id": f"avg_{col}",
                    "name": f"Average {clean_name}",
                    "title": f"Average {clean_name}",
                    "category": "Core Aggregation",
                    "expression": avg_expr,
                    "dax": avg_expr,
                    "type": "scalar",
                    "value": val,
                    "formatted": formatted_val,
                    "description": f"Calculates mean {clean_name} per transaction in {fact_table}."
                })
            except Exception:
                pass

        # 4. Total Volume
        count_expr = f"COUNTROWS({fact_table})"
        try:
            val = self.evaluate_scalar_dax(count_expr)
            auto_measures.append({
                "id": "count_records",
                "name": f"Total {fact_table} Volume",
                "title": f"Total {fact_table} Volume",
                "category": "Volume",
                "expression": count_expr,
                "dax": count_expr,
                "type": "scalar",
                "value": val,
                "formatted": f"{int(val):,} Records",
                "description": f"Census record volume for {fact_table}."
            })
        except Exception:
            pass

        # 5. Financial / Business Ratios (Margin, Conversion)
        profit_cols = [c for c in metric_cols if "profit" in c.lower() or "margin" in c.lower()]
        sales_cols = [c for c in metric_cols if "sales" in c.lower() or "revenue" in c.lower()]
        cost_cols = [c for c in metric_cols if "cost" in c.lower() or "expense" in c.lower() or "spend" in c.lower()]

        if profit_cols and sales_cols:
            p_col, s_col = profit_cols[0], sales_cols[0]
            ratio_expr = f"DIVIDE(SUM({fact_table}[{p_col}]), SUM({fact_table}[{s_col}]))"
            try:
                val = self.evaluate_scalar_dax(ratio_expr)
                auto_measures.append({
                    "id": "profit_margin",
                    "name": "Gross Profit Margin %",
                    "title": "Gross Profit Margin %",
                    "category": "Financial Ratio",
                    "expression": ratio_expr,
                    "dax": ratio_expr,
                    "type": "scalar",
                    "value": val,
                    "formatted": f"{val * 100:.2f}%",
                    "description": f"Ratio of total {p_col} over total {s_col}."
                })
            except Exception:
                pass

        if cost_cols and sales_cols:
            c_col, s_col = cost_cols[0], sales_cols[0]
            cost_ratio_expr = f"DIVIDE(SUM({fact_table}[{c_col}]), SUM({fact_table}[{s_col}]))"
            try:
                val = self.evaluate_scalar_dax(cost_ratio_expr)
                auto_measures.append({
                    "id": "cost_ratio",
                    "name": "Cost-to-Sales Ratio %",
                    "title": "Cost-to-Sales Ratio %",
                    "category": "Financial Ratio",
                    "expression": cost_ratio_expr,
                    "dax": cost_ratio_expr,
                    "type": "scalar",
                    "value": val,
                    "formatted": f"{val * 100:.2f}%",
                    "description": "Operating cost burden relative to top-line sales."
                })
            except Exception:
                pass

        # 6. Cross-Table Relational Summaries (SUMMARIZE)
        for rel in self.model.relationships:
            from_t = rel["from_table"]
            to_t = rel["to_table"]
            dim_table = to_t if from_t == fact_table else from_t
            dim_df = self.model.tables.get(dim_table)
            if dim_df is None:
                continue

            cat_cols = dim_df.select_dtypes(include=["object", "category", "string"]).columns.tolist()
            dim_candidates = [
                c for c in cat_cols 
                if not re.search(r'(?:_id|id$|^id$|code)', c.lower()) and 2 <= dim_df[c].nunique() <= 30
            ]
            if not dim_candidates and cat_cols:
                dim_candidates = cat_cols[:1]

            for dim_col in dim_candidates[:2]:
                if metric_cols:
                    m_col = metric_cols[0]
                    clean_m = m_col.replace("_", " ").title()
                    clean_d = dim_col.replace("_", " ").title()
                    summarize_expr = f'SUMMARIZE({fact_table}, {dim_table}[{dim_col}], "Total {clean_m}", SUM({fact_table}[{m_col}]))'
                    try:
                        summary_res = self.evaluate_summarize(summarize_expr)
                        auto_measures.append({
                            "id": f"sum_{dim_table}_{dim_col}_{m_col}",
                            "name": f"{clean_m} by {dim_table} {clean_d}",
                            "title": f"{clean_m} by {dim_table} {clean_d}",
                            "category": "Dimensional Breakdown",
                            "expression": summarize_expr,
                            "dax": summarize_expr,
                            "type": "table",
                            "chart": summary_res.get("chart"),
                            "rows_count": summary_res.get("total_rows", 0),
                            "description": f"Cross-table multi-dimensional breakdown of {clean_m} grouped by {dim_table}.{dim_col}."
                        })
                    except Exception:
                        pass

        return auto_measures

    def natural_language_to_dax(self, prompt: str) -> Dict[str, Any]:
        """
        Translates natural language conversational prompts into executable DAX queries.
        e.g. 'sales by customer region' -> SUMMARIZE(Orders, Customers[region], 'Total Sales', SUM(Orders[sales]))
        """
        prompt_clean = prompt.lower().strip()
        if not prompt_clean:
            raise ValueError("Prompt cannot be empty.")

        # If already explicit DAX syntax
        if re.search(r'\b(SUM|AVERAGE|DIVIDE|CALCULATE|SUMMARIZE|COUNTROWS)\s*\(', prompt, re.I):
            return {"dax": prompt.strip(), "confidence": 1.0, "explanation": "Direct DAX Expression"}

        # Determine Fact Table
        fact_candidates = sorted(
            self.model.tables.keys(),
            key=lambda t: (sum(1 for r in self.model.relationships if r["from_table"] == t), len(self.model.tables[t])),
            reverse=True
        )
        fact_table = fact_candidates[0] if fact_candidates else list(self.model.tables.keys())[0]
        fact_df = self.model.tables.get(fact_table, pd.DataFrame())

        # 1. Identify Target Metric Column
        target_col = None
        target_table = fact_table

        for t_name, df in self.model.tables.items():
            for col in df.columns:
                clean_col = col.lower().replace("_", " ")
                if clean_col in prompt_clean:
                    target_col = col
                    target_table = t_name
                    break
            if target_col:
                break

        if not target_col:
            num_cols = fact_df.select_dtypes(include=[np.number]).columns.tolist() if not fact_df.empty else []
            metric_cols = [c for c in num_cols if not re.search(r'(?:_id|id$|^id$|code|key)', c.lower())]
            target_col = metric_cols[0] if metric_cols else (num_cols[0] if num_cols else "sales")

        # 2. Check for Margin / Ratio keywords
        if "margin" in prompt_clean or "ratio" in prompt_clean:
            profit_cols = [c for c in fact_df.columns if "profit" in c.lower() or "margin" in c.lower()]
            sales_cols = [c for c in fact_df.columns if "sales" in c.lower() or "revenue" in c.lower()]
            if profit_cols and sales_cols:
                ratio_expr = f"DIVIDE(SUM({fact_table}[{profit_cols[0]}]), SUM({fact_table}[{sales_cols[0]}]))"
                m_by = re.search(r'\b(?:by|per|across)\s+([a-zA-Z0-9_\s]+)', prompt_clean)
                if m_by:
                    group_word = m_by.group(1).strip()
                    dim_col, dim_t = self._find_column_and_table(group_word)
                    if dim_col:
                        dax = f'SUMMARIZE({fact_table}, {dim_t}[{dim_col}], "Profit Margin", {ratio_expr})'
                        return {"dax": dax, "confidence": 0.95, "explanation": f"Grouped profit margin ratio by {dim_t}[{dim_col}]."}
                return {"dax": ratio_expr, "confidence": 0.95, "explanation": "Evaluates safe ratio of profit over sales."}

        # 3. Check for Grouping ('by', 'per', 'across')
        m_by = re.search(r'\b(?:by|per|across|for each)\s+([a-zA-Z0-9_\s]+)', prompt_clean)
        if m_by:
            group_candidate = m_by.group(1).strip()
            dim_col, dim_t = self._find_column_and_table(group_candidate)
            if dim_col:
                agg_func = "AVERAGE" if ("average" in prompt_clean or "avg" in prompt_clean or "mean" in prompt_clean) else "SUM"
                measure_title = f"{'Avg' if agg_func == 'AVERAGE' else 'Total'} {target_col.replace('_', ' ').title()}"
                dax = f'SUMMARIZE({fact_table}, {dim_t}[{dim_col}], "{measure_title}", {agg_func}({target_table}[{target_col}]))'
                return {"dax": dax, "confidence": 0.92, "explanation": f"Multi-dimensional summary of {measure_title} grouped by {dim_t}[{dim_col}]."}

        # 4. Check for Filter ('where', 'in', '=')
        m_filter = re.search(r'\bwhere\s+([a-zA-Z0-9_]+)\s*(?:is|=|equals)\s*[\'"]?([a-zA-Z0-9_\s]+)[\'"]?', prompt_clean)
        if m_filter:
            f_col_raw, f_val = m_filter.group(1).strip(), m_filter.group(2).strip()
            f_col, f_t = self._find_column_and_table(f_col_raw)
            if f_col:
                dax = f'CALCULATE(SUM({target_table}[{target_col}]), {f_t}[{f_col}] = "{f_val.title()}")'
                return {"dax": dax, "confidence": 0.90, "explanation": f"Context transition filter on {f_t}[{f_col}] = '{f_val}'."}

        # 5. Default scalar aggregation
        agg_func = "AVERAGE" if ("average" in prompt_clean or "mean" in prompt_clean) else ("COUNTROWS" if ("count" in prompt_clean or "rows" in prompt_clean or "volume" in prompt_clean) else "SUM")
        if agg_func == "COUNTROWS":
            dax = f"COUNTROWS({fact_table})"
        else:
            dax = f"{agg_func}({target_table}[{target_col}])"
        return {"dax": dax, "confidence": 0.88, "explanation": f"Calculates {agg_func} of {target_table}[{target_col}]."}


# ============================================================
# MULTI-FILE & MULTI-SHEET INGESTION CONTROLLER
# ============================================================

def ingest_files_into_model(files_data: List[Tuple[str, bytes]], model: DataModel, clear_existing: bool = False) -> Dict[str, Any]:
    """
    Ingests multiple files (CSV, TSV, or multi-sheet Excel workbooks)
    into the active DataModel and discovers inter-table schema relationships.
    """
    if clear_existing:
        model.clear()

    loaded_tables = []
    
    for filename, content in files_data:
        clean_base = re.sub(r'\.[a-zA-Z0-9]+$', '', filename).replace(" ", "_")
        
        # 1. Multi-Sheet Excel (.xlsx, .xls)
        if filename.lower().endswith(('.xlsx', '.xls')):
            try:
                excel_file = io.BytesIO(content)
                sheets = pd.read_excel(excel_file, sheet_name=None)
                for sheet_name, sheet_df in sheets.items():
                    if sheet_df is not None and not sheet_df.empty:
                        table_name = sheet_name.strip().replace(" ", "_")
                        if len(sheets) > 1 and clean_base.lower() not in table_name.lower():
                            table_name = f"{clean_base}_{table_name}"
                        model.add_table(table_name, sheet_df)
                        loaded_tables.append(table_name)
            except Exception as e:
                print(f"[Multi-Sheet Excel Load Error] {filename}: {e}", flush=True)

        # 2. CSV / TSV / TXT (Smart encoding and delimiter sniffing)
        elif filename.lower().endswith(('.csv', '.tsv', '.txt')):
            try:
                from engine.cleaner import sniff_and_read_csv
                df = sniff_and_read_csv(content, filename)
                if df is not None and not df.empty:
                    table_name = clean_base
                    model.add_table(table_name, df)
                    loaded_tables.append(table_name)
            except Exception as e:
                print(f"[Smart CSV Load Error] {filename}: {e}", flush=True)
                # Fallback to standard read_csv with latin1 and lenient parsing
                try:
                    df = pd.read_csv(io.BytesIO(content), encoding="latin1", on_bad_lines="skip")
                    if df is not None and not df.empty:
                        table_name = clean_base
                        model.add_table(table_name, df)
                        loaded_tables.append(table_name)
                except Exception as e2:
                    print(f"[CSV Fallback Error] {filename}: {e2}", flush=True)

        # 3. JSON
        elif filename.lower().endswith('.json'):
            try:
                df = pd.read_json(io.BytesIO(content))
                if df is not None and not df.empty:
                    table_name = clean_base
                    model.add_table(table_name, df)
                    loaded_tables.append(table_name)
            except Exception as e:
                print(f"[JSON Load Error] {filename}: {e}", flush=True)

    relationships = []
    try:
        relationships = model.detect_relationships()
    except Exception as e:
        print(f"[Detect Relationships Error] {e}", flush=True)

    # Automatically generate suggested DAX measures for the loaded model (safe, non-blocking)
    automated_measures = []
    try:
        dax_engine = DaxEngine(model)
        automated_measures = dax_engine.generate_automated_measures()
    except Exception as e:
        print(f"[Auto-Measures Generation Error] {e}", flush=True)

    try:
        schema_summary = model.get_schema_summary()
    except Exception as e:
        print(f"[Schema Summary Error] {e}", flush=True)
        schema_summary = {
            "tables": [],
            "relationships": model.relationships,
            "total_tables": len(model.tables),
            "measures_count": 0
        }

    return {
        "status": "success",
        "loaded_tables": loaded_tables,
        "relationships_discovered": relationships,
        "total_tables": len(model.tables),
        "schema": schema_summary,
        "automated_measures": automated_measures
    }
