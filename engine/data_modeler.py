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
        """
        discovered = []
        table_names = list(self.tables.keys())
        if len(table_names) < 2:
            return discovered

        for i in range(len(table_names)):
            for j in range(len(table_names)):
                if i == j:
                    continue
                t1, t2 = table_names[i], table_names[j]
                df1, df2 = self.tables[t1], self.tables[t2]

                for col1 in df1.columns:
                    c1_clean = col1.lower().replace("_", "").replace("-", "")
                    
                    for col2 in df2.columns:
                        c2_clean = col2.lower().replace("_", "").replace("-", "")
                        
                        t2_stem = re.sub(r'(?:ies|s)$', '', t2.lower())
                        t1_stem = re.sub(r'(?:ies|s)$', '', t1.lower())
                        is_match = False
                        if c1_clean == c2_clean and len(c1_clean) > 1:
                            is_match = True
                        elif c2_clean in ["id", f"{t2_stem}id"] and (t2_stem in c1_clean):
                            is_match = True
                        elif c1_clean in ["id", f"{t1_stem}id"] and (t1_stem in c2_clean):
                            is_match = True
                        elif (t2_stem and t2_stem in c1_clean) and (c2_clean == "id" or c2_clean in c1_clean):
                            is_match = True

                        if is_match:
                            # Verify value overlap to confirm true relationship
                            try:
                                s1 = df1[col1].dropna().astype(str).unique()
                                s2 = df2[col2].dropna().astype(str).unique()
                                if len(s1) > 0 and len(s2) > 0:
                                    overlap = len(set(s1).intersection(set(s2)))
                                    ratio = overlap / min(len(s1), len(s2))
                                    if ratio >= 0.25:  # Significant overlap found
                                        is_unique_in_t2 = (len(s2) == len(df2[col2].dropna()))
                                        cardinality = "many_to_one" if is_unique_in_t2 else "many_to_many"
                                        
                                        rel_entry = {
                                            "from_table": t1,
                                            "from_col": col1,
                                            "to_table": t2,
                                            "to_col": col2,
                                            "cardinality": cardinality,
                                            "overlap_ratio": round(ratio, 2)
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

            sample_rows = df.head(5).fillna("").to_dict(orient="records")
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

                    joined = pd.merge(
                        joined,
                        right_df,
                        how="left",
                        left_on=rel["from_col"],
                        right_on=right_key
                    )
                    visited_tables.add(to_t)
                    progress_made = True

                elif to_t in visited_tables and from_t not in visited_tables:
                    left_df = self.tables[from_t].copy()
                    rename_map = {
                        c: f"{from_t}_{c}" for c in left_df.columns if c != rel["from_col"] and c in joined.columns
                    }
                    left_df = left_df.rename(columns=rename_map)
                    left_key = rename_map.get(rel["from_col"], rel["from_col"])

                    joined = pd.merge(
                        joined,
                        left_df,
                        how="left",
                        left_on=rel["to_col"],
                        right_on=left_key
                    )
                    visited_tables.add(from_t)
                    progress_made = True

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
        if group_col in joined.columns:
            resolved_group_col = group_col
        else:
            for c in joined.columns:
                if c.endswith(f"_{group_col}") or c.lower() == group_col.lower():
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
        if primary_measure in res_df.columns:
            res_df = res_df.sort_values(by=primary_measure, ascending=False).head(20)

        labels = [str(x) for x in res_df[group_col].tolist()]
        values = [float(v) for v in res_df[primary_measure].tolist()]

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


# ============================================================
# MULTI-FILE & MULTI-SHEET INGESTION CONTROLLER
# ============================================================

def ingest_files_into_model(files_data: List[Tuple[str, bytes]], model: DataModel) -> Dict[str, Any]:
    """
    Ingests multiple files (CSV, TSV, or multi-sheet Excel workbooks)
    into the active DataModel and discovers inter-table schema relationships.
    """
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

        # 2. CSV / TSV
        elif filename.lower().endswith(('.csv', '.tsv', '.txt')):
            try:
                sep = '\t' if filename.lower().endswith('.tsv') else ','
                df = pd.read_csv(io.BytesIO(content), sep=sep, low_memory=False, encoding_errors="replace")
                if not df.empty:
                    table_name = clean_base
                    model.add_table(table_name, df)
                    loaded_tables.append(table_name)
            except Exception as e:
                print(f"[CSV Load Error] {filename}: {e}", flush=True)

        # 3. JSON
        elif filename.lower().endswith('.json'):
            try:
                df = pd.read_json(io.BytesIO(content))
                if not df.empty:
                    table_name = clean_base
                    model.add_table(table_name, df)
                    loaded_tables.append(table_name)
            except Exception as e:
                print(f"[JSON Load Error] {filename}: {e}", flush=True)

    relationships = model.detect_relationships()

    return {
        "status": "success",
        "loaded_tables": loaded_tables,
        "relationships_discovered": relationships,
        "total_tables": len(model.tables),
        "schema": model.get_schema_summary()
    }
