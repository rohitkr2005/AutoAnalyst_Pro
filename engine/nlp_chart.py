"""
AutoAnalyst Pro - Natural Language "Text-to-Chart" BI Engine
Parses natural language requests (e.g. "Average heart rate by gender as a bar chart",
"Scatter plot of age vs blood pressure", "Distribution of revenue") and automatically
computes the statistical aggregation and Chart.js configuration with executive narratives.
"""

import re
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple


CHART_PALETTES = [
    '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899',
    '#8b5cf6', '#3b82f6', '#14b8a6', '#f43f5e', '#a855f7'
]


def _find_best_column_match(query: str, columns: List[str]) -> Optional[str]:
    """Finds the best matching column name from a natural language query."""
    q = query.lower()
    # 1. Exact or whole-word match
    for col in columns:
        col_clean = str(col).lower().replace('_', ' ')
        if re.search(r'\b' + re.escape(col_clean) + r'\b', q) or col.lower() in q:
            return col
            
    # 2. Token overlap match
    words = set(re.findall(r'\w+', q))
    best_col = None
    best_score = 0
    for col in columns:
        col_words = set(str(col).lower().replace('_', ' ').split())
        overlap = len(words.intersection(col_words))
        if overlap > best_score:
            best_score = overlap
            best_col = col
            
    return best_col if best_score > 0 else None


def generate_text_to_chart(prompt: str, df: pd.DataFrame, eda_cache: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Synthesizes a natural language prompt into a full Chart.js dataset and executive insight.
    """
    if df is None or len(df) == 0:
        return {
            "status": "error",
            "message": "No active dataset loaded. Please load a dataset first."
        }

    q = prompt.lower().strip()
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    categorical_cols = list(df.select_dtypes(include=[object, "string", "category"]).columns)
    datetime_cols = list(df.select_dtypes(include=["datetime64[ns]", "datetime"]).columns)
    all_cols = list(df.columns)

    # 1. Detect Chart Type
    chart_type = "bar"
    if any(w in q for w in ["scatter", "correlation", "versus", "vs", "against"]):
        chart_type = "scatter"
    elif any(w in q for w in ["pie", "doughnut", "donut", "share", "proportion", "breakdown"]):
        chart_type = "doughnut" if "doughnut" in q or "donut" in q else "pie"
    elif any(w in q for w in ["line", "trend", "temporal", "over time", "trajectory"]):
        chart_type = "line"
    elif any(w in q for w in ["radar", "spider"]):
        chart_type = "radar"
    elif any(w in q for w in ["horizontal", "ranking", "leaders", "top"]):
        chart_type = "horizontalBar"
    elif any(w in q for w in ["hist", "histogram", "distribution", "spread"]):
        chart_type = "distribution"

    # 2. Detect Aggregation Function
    agg_func = "mean"
    agg_name = "Average"
    if any(w in q for w in ["sum", "total", "cumulative", "aggregate"]):
        agg_func = "sum"
        agg_name = "Total"
    elif any(w in q for w in ["count", "number of", "frequency", "how many"]):
        agg_func = "count"
        agg_name = "Count"
    elif any(w in q for w in ["median", "middle"]):
        agg_func = "median"
        agg_name = "Median"
    elif any(w in q for w in ["max", "maximum", "peak", "highest"]):
        agg_func = "max"
        agg_name = "Maximum"
    elif any(w in q for w in ["min", "minimum", "lowest"]):
        agg_func = "min"
        agg_name = "Minimum"

    # 3. Handle Scatter Plot
    if chart_type == "scatter":
        # Look for two numeric columns (e.g. "age vs heart rate")
        matched_cols = []
        for col in numeric_cols:
            col_clean = str(col).lower().replace('_', ' ')
            if col_clean in q or str(col).lower() in q:
                matched_cols.append(col)
        
        x_col = matched_cols[0] if len(matched_cols) > 0 else (numeric_cols[0] if numeric_cols else None)
        y_col = matched_cols[1] if len(matched_cols) > 1 else (numeric_cols[1] if len(numeric_cols) > 1 else x_col)

        if not x_col or not y_col:
            return {"status": "error", "message": "Scatter plots require at least one numeric dimension."}

        scatter_df = df[[x_col, y_col]].dropna().head(300)
        points = [{"x": float(row[x_col]), "y": float(row[y_col])} for _, row in scatter_df.iterrows()]
        
        # Calculate Pearson r
        corr_val = float(scatter_df[x_col].corr(scatter_df[y_col])) if len(scatter_df) > 2 else 0.0
        corr_str = f"r = {corr_val:.2f}"
        
        return {
            "status": "success",
            "chart_type": "scatter",
            "title": f"Bivariate Scatter: {x_col} vs {y_col} ({corr_str})",
            "metric": y_col,
            "dimension": x_col,
            "labels": [str(p["x"]) for p in points],
            "datasets": [{
                "label": f"{y_col} vs {x_col}",
                "data": points,
                "backgroundColor": "rgba(99, 102, 241, 0.65)",
                "borderColor": "#6366f1",
                "pointRadius": 4.5,
                "pointHoverRadius": 7
            }],
            "narrative": (
                f"Statistical correlation between **{x_col}** and **{y_col}** yields **{corr_str}**. "
                f"The scatter distribution demonstrates "
                f"{'a moderate to strong direct linear pattern' if abs(corr_val) > 0.4 else 'a dispersed non-linear spread'}."
            )
        }

    # 4. Handle Distribution / Histogram
    if chart_type == "distribution":
        target_col = _find_best_column_match(q, numeric_cols) or (numeric_cols[0] if numeric_cols else None)
        if not target_col:
            return {"status": "error", "message": "No numeric column found for distribution plot."}
            
        series = df[target_col].dropna()
        counts, bin_edges = np.histogram(series, bins=12)
        bin_labels = [f"{bin_edges[i]:.1f} - {bin_edges[i+1]:.1f}" for i in range(len(counts))]
        
        return {
            "status": "success",
            "chart_type": "bar",
            "title": f"Distribution Histogram: {target_col}",
            "metric": target_col,
            "dimension": "Bins",
            "labels": bin_labels,
            "datasets": [{
                "label": f"Frequency ({target_col})",
                "data": [int(c) for c in counts],
                "backgroundColor": "rgba(6, 182, 212, 0.55)",
                "borderColor": "#06b6d4",
                "borderWidth": 1.5
            }],
            "narrative": (
                f"Histogram of **{target_col}** across {len(series):,} records. "
                f"Mean: **{series.mean():.2f}**, Median: **{series.median():.2f}**, "
                f"Peak frequency cluster observed around bin **{bin_labels[int(np.argmax(counts))]}**."
            )
        }

    # 5. Handle Grouped Metrics (Bar, Line, Doughnut, Pie)
    # Find metric (numeric) and dimension (categorical/date)
    target_metric = _find_best_column_match(q, numeric_cols)
    target_dimension = _find_best_column_match(q, categorical_cols + datetime_cols)

    # Smart fallbacks if user didn't mention both
    if not target_metric and numeric_cols:
        target_metric = numeric_cols[0]
    if not target_dimension and categorical_cols:
        target_dimension = categorical_cols[0]
    elif not target_dimension and datetime_cols:
        target_dimension = datetime_cols[0]

    if not target_dimension:
        # If no categorical dimension, group by first column or index
        target_dimension = all_cols[0]

    # Perform pandas GroupBy aggregation
    try:
        if agg_func == "count":
            grouped = df.groupby(target_dimension).size().reset_index(name="count")
            metric_col_name = "count"
        else:
            if target_metric:
                grouped = df.groupby(target_dimension)[target_metric].agg(agg_func).reset_index()
                metric_col_name = target_metric
            else:
                grouped = df.groupby(target_dimension).size().reset_index(name="count")
                metric_col_name = "count"

        # Sort and limit top categories for visual excellence
        grouped = grouped.sort_values(by=metric_col_name, ascending=False).head(16)
        labels = [str(x) for x in grouped[target_dimension].tolist()]
        values = [round(float(v), 2) for v in grouped[metric_col_name].tolist()]

    except Exception as e:
        return {"status": "error", "message": f"Could not group data: {str(e)}"}

    # Assign attractive modern palette
    if chart_type in ["pie", "doughnut"]:
        bg_colors = CHART_PALETTES[:len(labels)]
        border_colors = [c for c in bg_colors]
    elif chart_type == "line":
        bg_colors = "rgba(99, 102, 241, 0.15)"
        border_colors = "#6366f1"
    else:
        bg_colors = [CHART_PALETTES[i % len(CHART_PALETTES)] for i in range(len(labels))]
        border_colors = bg_colors

    chart_title = f"{agg_name} {target_metric or ''} by {target_dimension}".strip()
    
    # Executive Narrative Synthesis
    if len(values) > 0:
        max_idx = int(np.argmax(values))
        min_idx = int(np.argmin(values))
        lead_label = labels[max_idx]
        lead_val = values[max_idx]
        tail_label = labels[min_idx]
        tail_val = values[min_idx]
        
        narrative = (
            f"**{lead_label}** leads with the highest {agg_name.lower()} of **{lead_val:,.1f}**, "
            f"while **{tail_label}** records **{tail_val:,.1f}**. "
            f"Overall, {len(labels)} categories were synthesized with a spread ratio of "
            f"**{(lead_val / (tail_val + 1e-6)):.1f}x**."
        )
    else:
        narrative = f"Generated {chart_title} across available records."

    return {
        "status": "success",
        "chart_type": "bar" if chart_type == "horizontalBar" else chart_type,
        "is_horizontal": chart_type == "horizontalBar",
        "title": chart_title,
        "metric": target_metric,
        "dimension": target_dimension,
        "aggregation": agg_name,
        "labels": labels,
        "datasets": [{
            "label": f"{agg_name} of {target_metric or 'Count'}",
            "data": values,
            "backgroundColor": bg_colors,
            "borderColor": border_colors,
            "borderWidth": 1.5,
            "fill": chart_type == "line"
        }],
        "narrative": narrative
    }
