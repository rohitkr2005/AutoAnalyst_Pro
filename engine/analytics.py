"""
AutoAnalyst Pro - Statistical Profiling & Exploratory Data Analysis (EDA) Engine
Computes univariate statistics, categorical cardinality/Pareto distributions,
Pearson & Spearman correlation heatmaps, distribution bins for charts, and group-by aggregations.
"""

import numpy as np
import pandas as pd
from scipy import stats
from typing import Dict, List, Any, Optional


def compute_comprehensive_eda(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes full exploratory data analysis metrics, statistical summaries,
    correlation matrices, and chart-ready distribution histograms.
    """
    n_rows, n_cols = df.shape
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    # Filter out internal/engineered non-metric columns from primary stats if needed, but include all
    categorical_cols = list(df.select_dtypes(include=[object, "string", "category"]).columns)
    datetime_cols = list(df.select_dtypes(include=["datetime64[ns]", "datetime"]).columns)

    # 1. Univariate Numerical Statistics
    num_stats = {}
    distributions = {}
    for col in numeric_cols:
        series = df[col].dropna()
        if len(series) == 0:
            continue
            
        mean_val = float(series.mean())
        median_val = float(series.median())
        std_val = float(series.std(ddof=1)) if len(series) > 1 else 0.0
        var_val = float(series.var(ddof=1)) if len(series) > 1 else 0.0
        min_val = float(series.min())
        max_val = float(series.max())
        q25 = float(series.quantile(0.25))
        q75 = float(series.quantile(0.75))
        iqr_val = float(q75 - q25)
        
        # Skewness and Kurtosis (guard against near-zero variance)
        skew_val = 0.0
        kurt_val = 0.0
        if len(series) > 3 and std_val > 1e-4:
            try:
                skew_val = float(stats.skew(series, bias=False))
                kurt_val = float(stats.kurtosis(series, bias=False))
                if np.isnan(skew_val) or np.isinf(skew_val):
                    skew_val = 0.0
                if np.isnan(kurt_val) or np.isinf(kurt_val):
                    kurt_val = 0.0
            except Exception:
                skew_val = 0.0
                kurt_val = 0.0

        # Distribution shape assessment
        dist_shape = "Normal / Symmetrical"
        if abs(skew_val) > 1.0:
            dist_shape = "Highly Skewed (" + ("Right/Positive" if skew_val > 0 else "Left/Negative") + ")"
        elif abs(skew_val) > 0.5:
            dist_shape = "Moderately Skewed"

        num_stats[col] = {
            "name": col,
            "count": int(len(series)),
            "missing": int(df[col].isna().sum()),
            "mean": round(mean_val, 2),
            "median": round(median_val, 2),
            "std": round(std_val, 2),
            "variance": round(var_val, 2),
            "min": round(min_val, 2),
            "q25": round(q25, 2),
            "q75": round(q75, 2),
            "max": round(max_val, 2),
            "iqr": round(iqr_val, 2),
            "skewness": round(skew_val, 3),
            "kurtosis": round(kurt_val, 3),
            "distribution_shape": dist_shape
        }

        # Histogram Bins for Chart.js
        if len(series) >= 4 and min_val < max_val:
            n_bins = min(20, max(6, int(np.sqrt(len(series)))))
            hist_counts, bin_edges = np.histogram(series, bins=n_bins)
            bin_labels = [f"{round(bin_edges[i], 1)} - {round(bin_edges[i+1], 1)}" for i in range(len(hist_counts))]
            distributions[col] = {
                "labels": bin_labels,
                "counts": [int(c) for c in hist_counts],
                "min": min_val,
                "max": max_val
            }

    # 2. Categorical Statistics & Frequency Distributions
    cat_stats = {}
    for col in categorical_cols:
        series = df[col].dropna().astype(str)
        if len(series) == 0:
            continue
            
        val_counts = series.value_counts()
        total_non_null = len(series)
        top_n = val_counts.head(10)
        
        freq_list = []
        cumulative_pct = 0.0
        for category, count in top_n.items():
            pct = round((count / total_non_null) * 100, 1)
            cumulative_pct += pct
            freq_list.append({
                "category": str(category),
                "count": int(count),
                "percentage": pct,
                "cumulative_pct": round(cumulative_pct, 1)
            })

        cat_stats[col] = {
            "name": col,
            "unique_count": int(series.nunique()),
            "missing": int(df[col].isna().sum()),
            "top_category": str(val_counts.index[0]) if len(val_counts) > 0 else "N/A",
            "top_category_count": int(val_counts.iloc[0]) if len(val_counts) > 0 else 0,
            "frequency_distribution": freq_list
        }

    # 3. Correlation Analysis (Pearson & Spearman)
    correlation_data = {
        "columns": [],
        "pearson_matrix": [],
        "spearman_matrix": [],
        "top_correlations": []
    }
    
    # Select clean continuous numeric columns (filter out ID-like columns)
    corr_cols = [c for c in numeric_cols if not c.endswith(("_Year", "_IsWeekend")) and "id" not in c.lower() and df[c].nunique() > 5]
    if len(corr_cols) >= 2:
        clean_subset = df[corr_cols].dropna()
        if len(clean_subset) >= 5:
            pearson_df = clean_subset.corr(method="pearson").round(3)
            spearman_df = clean_subset.corr(method="spearman").round(3)

            # Replace any NaNs with 0
            pearson_df = pearson_df.fillna(0)
            spearman_df = spearman_df.fillna(0)

            correlation_data["columns"] = list(corr_cols)
            correlation_data["pearson_matrix"] = pearson_df.values.tolist()
            correlation_data["spearman_matrix"] = spearman_df.values.tolist()

            # Rank top correlations (ignoring diagonal and duplicate pairs)
            pairs = []
            for i in range(len(corr_cols)):
                for j in range(i + 1, len(corr_cols)):
                    col_a = corr_cols[i]
                    col_b = corr_cols[j]
                    p_val = float(pearson_df.iloc[i, j])
                    s_val = float(spearman_df.iloc[i, j])
                    strength = "Weak"
                    if abs(p_val) >= 0.7:
                        strength = "Strong"
                    elif abs(p_val) >= 0.4:
                        strength = "Moderate"

                    direction = "Positive" if p_val > 0 else "Negative"

                    pairs.append({
                        "feature_a": col_a,
                        "feature_b": col_b,
                        "pearson_r": round(p_val, 3),
                        "spearman_rho": round(s_val, 3),
                        "strength": strength,
                        "direction": direction,
                        "abs_val": abs(p_val)
                    })

            pairs.sort(key=lambda x: x["abs_val"], reverse=True)
            correlation_data["top_correlations"] = pairs[:8]

    # 4. Automatic Cross-Tabulation / Group-by Aggregations
    # Pair top category with top numeric metric (e.g. Sales by Category)
    groupby_insights = []
    if len(categorical_cols) > 0 and len(corr_cols) > 0:
        for cat_col in categorical_cols[:3]:
            # Select category with reasonable cardinality (2 to 15 unique values)
            if 2 <= df[cat_col].nunique() <= 15:
                num_col = corr_cols[0] # primary metric
                grouped = df.groupby(cat_col)[num_col].agg(["count", "sum", "mean", "median"]).reset_index()
                grouped = grouped.sort_values(by="sum", ascending=False).head(10)
                
                rows = []
                for _, r in grouped.iterrows():
                    rows.append({
                        "segment": str(r[cat_col]),
                        "count": int(r["count"]),
                        "sum": round(float(r["sum"]), 2),
                        "mean": round(float(r["mean"]), 2),
                        "median": round(float(r["median"]), 2)
                    })
                groupby_insights.append({
                    "categorical_feature": cat_col,
                    "numerical_metric": num_col,
                    "rows": rows
                })

    return {
        "total_rows": n_rows,
        "total_cols": n_cols,
        "numeric_stats": num_stats,
        "categorical_stats": cat_stats,
        "distributions": distributions,
        "correlation": correlation_data,
        "groupby_insights": groupby_insights
    }
