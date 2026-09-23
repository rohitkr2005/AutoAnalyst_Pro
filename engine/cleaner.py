"""
AutoAnalyst Pro - Data Cleaning & Preprocessing Engine
Handles raw, messy, real-world data: sniffs formats, audits data quality,
cleans dirty numerics, parses mixed datetimes, imputes missing values,
treats outliers, standardizes text, and produces before-vs-after audit logs.
"""

import io
import re
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Any, Optional

IMPLICIT_NULL_STRINGS = {
    "", " ", "  ", "n/a", "na", "null", "none", "nan", "?", "-", "--", 
    "unknown", "pending", "pending...", "missing", "zero", "$ - ", "free", "call for price", "0000-00-00"
}


def sniff_and_read_csv(file_content: bytes, filename: str = "") -> pd.DataFrame:
    """
    Intelligently reads raw bytes from CSV, TSV, or Excel, auto-detecting delimiters and encodings.
    """
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_content))
    
    if filename.lower().endswith(".json"):
        try:
            return pd.read_json(io.BytesIO(file_content))
        except Exception:
            return pd.read_json(io.BytesIO(file_content), lines=True)

    # Decode bytes using common encodings
    text = None
    for enc in ["utf-8", "utf-8-sig", "latin1", "cp1252", "iso-8859-1"]:
        try:
            text = file_content.decode(enc)
            break
        except UnicodeDecodeError:
            continue
            
    if text is None:
        text = file_content.decode("utf-8", errors="replace")

    # Sniff delimiter
    first_few_lines = "\n".join([line for line in text.splitlines()[:15] if line.strip()])
    delimiters = [",", "\t", ";", "|"]
    best_delim = ","
    max_cols = 0
    for d in delimiters:
        try:
            counts = [line.count(d) for line in first_few_lines.splitlines() if line]
            if counts and min(counts) > 0 and len(set(counts)) <= 2:
                if counts[0] > max_cols:
                    max_cols = counts[0]
                    best_delim = d
        except Exception:
            continue

    try:
        df = pd.read_csv(io.StringIO(text), sep=best_delim, engine="python")
    except Exception:
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python")
        
    return df


def audit_dataset_health(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Performs an in-depth data quality audit on a DataFrame.
    Calculates health scores, missingness, duplicates, outliers, casing variations, and dirty types.
    """
    n_rows, n_cols = df.shape
    if n_rows == 0:
        return {"health_score": 0, "total_rows": 0, "total_cols": 0, "columns": {}}

    duplicate_rows = int(df.duplicated().sum())
    total_cells = n_rows * n_cols
    
    col_audits = {}
    total_missing_cells = 0
    total_outlier_count = 0
    dirty_type_cols = 0
    casing_anomalies_cols = 0

    for col in df.columns:
        series = df[col]
        # Detect explicit and implicit nulls
        missing_mask = series.isna()
        
        # Check string representations of nulls
        str_series = series.astype(str).str.strip().str.lower()
        implicit_mask = str_series.isin(IMPLICIT_NULL_STRINGS)
        combined_missing_mask = missing_mask | implicit_mask
        missing_count = int(combined_missing_mask.sum())
        total_missing_cells += missing_count
        missing_pct = round((missing_count / n_rows) * 100, 2)

        # Detect prospective data types
        non_null_vals = series[~combined_missing_mask]
        detected_type = "string"
        is_dirty_numeric = False
        is_dirty_datetime = False
        outlier_count = 0
        casing_variations = 0

        if len(non_null_vals) > 0:
            # Check if numeric or dirty numeric (e.g. contains $, %, commas, USD)
            cleaned_num_candidate = non_null_vals.astype(str).str.replace(r"[\$,€£¥%]", "", regex=True)
            cleaned_num_candidate = cleaned_num_candidate.str.replace(r"\b(usd|eur|gbp|sqft|sq\s*ft|mg/dl|kg|lbs|mmHg)\b", "", case=False, regex=True).str.strip()
            
            num_converted = pd.to_numeric(cleaned_num_candidate, errors="coerce")
            valid_num_ratio = num_converted.notna().sum() / len(non_null_vals)
            
            if valid_num_ratio > 0.75:
                if pd.api.types.is_numeric_dtype(series):
                    detected_type = "numeric"
                else:
                    detected_type = "dirty_numeric"
                    is_dirty_numeric = True
                    dirty_type_cols += 1
                
                # Check outliers on valid numeric values
                valid_nums = num_converted.dropna()
                if len(valid_nums) >= 4:
                    q25 = valid_nums.quantile(0.25)
                    q75 = valid_nums.quantile(0.75)
                    iqr = q75 - q25
                    lower_fence = q25 - 1.5 * iqr
                    upper_fence = q75 + 1.5 * iqr
                    outliers = valid_nums[(valid_nums < lower_fence) | (valid_nums > upper_fence)]
                    outlier_count = int(len(outliers))
                    total_outlier_count += outlier_count
            else:
                # Check if datetime candidate
                if not pd.api.types.is_numeric_dtype(series):
                    try:
                        # Sample 20 items to test datetime conversion speed
                        sample_vals = non_null_vals.head(20).astype(str)
                        parsed_sample = pd.to_datetime(sample_vals, errors="coerce", format="mixed")
                        if (parsed_sample.notna().sum() / len(sample_vals)) > 0.75:
                            detected_type = "datetime"
                            if not pd.api.types.is_datetime64_any_dtype(series):
                                is_dirty_datetime = True
                                dirty_type_cols += 1
                    except Exception:
                        pass
                        
            # Check casing variations in text columns
            if detected_type == "string":
                unique_exact = non_null_vals.astype(str).nunique()
                unique_lower = non_null_vals.astype(str).str.strip().str.lower().nunique()
                if unique_exact > unique_lower:
                    casing_variations = unique_exact - unique_lower
                    casing_anomalies_cols += 1

        col_audits[str(col)] = {
            "name": str(col),
            "detected_type": detected_type,
            "raw_dtype": str(series.dtype),
            "missing_count": missing_count,
            "missing_pct": missing_pct,
            "unique_count": int(series.nunique(dropna=True)),
            "outlier_count": outlier_count,
            "is_dirty_numeric": is_dirty_numeric,
            "is_dirty_datetime": is_dirty_datetime,
            "casing_variations": casing_variations
        }

    # Calculate Holistic Data Quality Score (0 to 100)
    missing_ratio = total_missing_cells / max(1, total_cells)
    dup_ratio = duplicate_rows / max(1, n_rows)
    dirty_ratio = dirty_type_cols / max(1, n_cols)
    outlier_ratio = min(1.0, total_outlier_count / max(1, total_cells))

    # Weightings: Completeness (40%), Uniqueness (20%), Schema/Type Consistency (25%), Outlier/Value Integrity (15%)
    score = 100.0 - (missing_ratio * 40.0) - (dup_ratio * 20.0) - (dirty_ratio * 25.0) - (outlier_ratio * 15.0)
    health_score = max(5.0, min(100.0, round(score, 1)))

    return {
        "health_score": health_score,
        "total_rows": n_rows,
        "total_cols": n_cols,
        "total_cells": total_cells,
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": round((duplicate_rows / max(1, n_rows)) * 100, 2),
        "total_missing_cells": total_missing_cells,
        "missing_cell_pct": round((total_missing_cells / max(1, total_cells)) * 100, 2),
        "total_outliers": total_outlier_count,
        "dirty_type_cols": dirty_type_cols,
        "casing_anomalies_cols": casing_anomalies_cols,
        "columns": col_audits
    }


def clean_and_preprocess(
    df: pd.DataFrame, 
    config: Optional[Dict[str, Any]] = None
) -> Tuple[pd.DataFrame, Dict[str, Any], str]:
    """
    Executes the automated cleaning and preprocessing pipeline on raw data:
    1. Deduplication
    2. Implicit null standardization
    3. Dirty numeric sanitization (stripping symbols, currencies, commas)
    4. Composite string decomposition (e.g. Blood Pressure '120/80')
    5. Multi-format datetime parsing & temporal feature extraction
    6. Text normalization (whitespace, casing)
    7. Missing value imputation (Median for numeric, Mode for categorical)
    8. Outlier treatment (Winsorization at 1st & 99th percentiles)
    
    Returns:
    - cleaned_df: Cleaned and structured Pandas DataFrame
    - audit_report: Before-vs-after comparison, transformation log, metric deltas
    - python_script: Executable Python code to reproduce the pipeline
    """
    if config is None:
        config = {
            "remove_duplicates": True,
            "clean_dirty_numerics": True,
            "standardize_text": True,
            "parse_dates": True,
            "extract_temporal_features": True,
            "impute_missing": True,
            "numeric_impute_strategy": "median",  # 'median', 'mean', 'zero', 'drop'
            "categorical_impute_strategy": "mode", # 'mode', 'unknown'
            "treat_outliers": True,
            "outlier_strategy": "winsorize",      # 'winsorize', 'clip_iqr', 'none'
            "decompose_composites": True
        }

    raw_audit = audit_dataset_health(df)
    clean_df = df.copy()
    transform_log = []
    
    # 1. Deduplication
    if config.get("remove_duplicates", True):
        initial_count = len(clean_df)
        clean_df = clean_df.drop_duplicates().reset_index(drop=True)
        dropped_dups = initial_count - len(clean_df)
        if dropped_dups > 0:
            transform_log.append(f"Purged {dropped_dups} duplicate rows from the dataset.")

    # 2. Standardize implicit nulls to np.nan
    for col in clean_df.columns:
        if clean_df[col].dtype == object or clean_df[col].dtype == "string":
            mask = clean_df[col].astype(str).str.strip().str.lower().isin(IMPLICIT_NULL_STRINGS)
            if mask.any():
                clean_df.loc[mask, col] = np.nan
                transform_log.append(f"Standardized {mask.sum()} implicit null values in column '{col}'.")

    # 3. Composite string decomposition (e.g., Blood Pressure '120/80 mmHg')
    if config.get("decompose_composites", True):
        for col in clean_df.columns:
            if clean_df[col].dtype == object:
                sample_str = clean_df[col].dropna().astype(str).head(20)
                # Check for blood pressure like "120/80"
                bp_pattern = re.compile(r"(\d{2,3})\s*/\s*(\d{2,3})")
                matches = sample_str.apply(lambda s: bool(bp_pattern.search(s)))
                if matches.sum() / max(1, len(sample_str)) > 0.6:
                    # Decompose
                    extracted = clean_df[col].astype(str).str.extract(r"(\d{2,3})\s*/\s*(\d{2,3})")
                    clean_df[f"{col}_Systolic"] = pd.to_numeric(extracted[0], errors="coerce")
                    clean_df[f"{col}_Diastolic"] = pd.to_numeric(extracted[1], errors="coerce")
                    clean_df = clean_df.drop(columns=[col])
                    transform_log.append(f"Decomposed composite column '{col}' into '{col}_Systolic' and '{col}_Diastolic'.")
                    break

    # 4. Dirty Numeric Sanitization
    if config.get("clean_dirty_numerics", True):
        for col in list(clean_df.columns):
            if clean_df[col].dtype == object:
                non_null = clean_df[col].dropna().astype(str)
                if len(non_null) == 0:
                    continue
                # Test numeric conversion after stripping symbols
                stripped = non_null.str.replace(r"[\$,€£¥%]", "", regex=True)
                stripped = stripped.str.replace(r"\b(usd|eur|gbp|sqft|sq\s*ft|mg/dl|kg|lbs|mmhg)\b", "", case=False, regex=True).str.strip()
                # Check if majority converts to numeric
                converted = pd.to_numeric(stripped, errors="coerce")
                if (converted.notna().sum() / len(non_null)) > 0.70:
                    clean_df[col] = pd.to_numeric(
                        clean_df[col].astype(str).str.replace(r"[\$,€£¥%]", "", regex=True)
                        .str.replace(r"\b(usd|eur|gbp|sqft|sq\s*ft|mg/dl|kg|lbs|mmhg)\b", "", case=False, regex=True)
                        .str.strip(),
                        errors="coerce"
                    )
                    transform_log.append(f"Sanitized and converted dirty string column '{col}' to numeric (float).")

    # 5. Multi-format DateTime Parsing & Feature Extraction
    if config.get("parse_dates", True):
        for col in list(clean_df.columns):
            if clean_df[col].dtype == object:
                non_null = clean_df[col].dropna().astype(str)
                if len(non_null) == 0:
                    continue
                
                # Check if matches common date formats
                is_date = False
                try:
                    sample = non_null.head(25)
                    parsed_sample = pd.to_datetime(sample, errors="coerce", format="mixed")
                    if (parsed_sample.notna().sum() / len(sample)) > 0.70:
                        is_date = True
                except Exception:
                    pass

                if is_date:
                    try:
                        clean_df[col] = pd.to_datetime(clean_df[col], errors="coerce", format="mixed")
                        transform_log.append(f"Parsed mixed-format dates in column '{col}' into ISO-8601 timestamps.")
                        
                        # Extract temporal features if configured
                        if config.get("extract_temporal_features", True):
                            clean_df[f"{col}_Year"] = clean_df[col].dt.year
                            clean_df[f"{col}_Month"] = clean_df[col].dt.month
                            clean_df[f"{col}_DayOfWeek"] = clean_df[col].dt.day_name()
                            clean_df[f"{col}_IsWeekend"] = clean_df[col].dt.dayofweek.isin([5, 6]).astype(int)
                            transform_log.append(f"Engineered temporal features ({col}_Year, {col}_Month, {col}_DayOfWeek, {col}_IsWeekend).")
                    except Exception as e:
                        pass

    # 6. Text Normalization
    if config.get("standardize_text", True):
        for col in clean_df.columns:
            if clean_df[col].dtype == object:
                # Trim whitespace, collapse multiple spaces, standardize case
                s = clean_df[col].astype(str)
                s = s.str.strip().str.replace(r"\s+", " ", regex=True)
                # If values are mixed case representation of categories (e.g. 'new york' vs 'New York'), title case them
                if s.nunique() < len(s) * 0.5:
                    clean_df[col] = s.str.title()
                else:
                    clean_df[col] = s
                # Restore actual NaN
                clean_df.loc[clean_df[col].str.lower().isin(IMPLICIT_NULL_STRINGS), col] = np.nan
                transform_log.append(f"Normalized casing and trimmed whitespace for text column '{col}'.")

    # 7. Outlier Treatment (Before imputation to avoid distorting median/mean)
    treated_outliers_count = 0
    if config.get("treat_outliers", True):
        strategy = config.get("outlier_strategy", "winsorize")
        num_cols = clean_df.select_dtypes(include=[np.number]).columns
        for col in num_cols:
            # Skip ID columns and binary flags
            if col.endswith("_Year") or col.endswith("_IsWeekend") or "id" in col.lower() or clean_df[col].nunique() <= 3:
                continue
                
            series = clean_df[col].dropna()
            if len(series) >= 10:
                q25 = series.quantile(0.25)
                q75 = series.quantile(0.75)
                iqr = q75 - q25
                if iqr > 0:
                    lower_b = q25 - 2.5 * iqr
                    upper_b = q75 + 2.5 * iqr
                    outlier_mask = (clean_df[col] < lower_b) | (clean_df[col] > upper_b)
                    cnt = outlier_mask.sum()
                    if cnt > 0:
                        treated_outliers_count += cnt
                        if strategy == "winsorize":
                            p01 = series.quantile(0.01)
                            p99 = series.quantile(0.99)
                            clean_df[col] = clean_df[col].clip(lower=p01, upper=p99)
                            transform_log.append(f"Winsorized {cnt} extreme outliers in '{col}' at 1st and 99th percentiles.")
                        elif strategy == "clip_iqr":
                            clean_df[col] = clean_df[col].clip(lower=lower_b, upper=upper_b)
                            transform_log.append(f"Clipped {cnt} outliers in '{col}' within 2.5x IQR boundaries.")

    # 8. Missing Value Imputation
    if config.get("impute_missing", True):
        num_strat = config.get("numeric_impute_strategy", "median")
        cat_strat = config.get("categorical_impute_strategy", "mode")
        
        # Impute numeric
        for col in clean_df.select_dtypes(include=[np.number]).columns:
            if clean_df[col].isna().any():
                imputed_val = 0
                if num_strat == "median":
                    imputed_val = clean_df[col].median()
                    clean_df[col] = clean_df[col].fillna(imputed_val)
                elif num_strat == "mean":
                    imputed_val = round(clean_df[col].mean(), 2)
                    clean_df[col] = clean_df[col].fillna(imputed_val)
                elif num_strat == "zero":
                    clean_df[col] = clean_df[col].fillna(0)
                transform_log.append(f"Imputed missing numeric values in '{col}' using {num_strat} ({imputed_val}).")

        # Impute categorical / strings
        for col in clean_df.select_dtypes(include=[object, "string"]).columns:
            if clean_df[col].isna().any():
                if cat_strat == "mode":
                    mode_vals = clean_df[col].mode()
                    val = mode_vals.iloc[0] if len(mode_vals) > 0 else "Unknown"
                    clean_df[col] = clean_df[col].fillna(val)
                    transform_log.append(f"Imputed missing categorical entries in '{col}' with mode ('{val}').")
                else:
                    clean_df[col] = clean_df[col].fillna("Unknown")
                    transform_log.append(f"Imputed missing categorical entries in '{col}' with 'Unknown'.")

    # Post-cleaning health audit
    cleaned_audit = audit_dataset_health(clean_df)

    audit_report = {
        "initial_health_score": raw_audit["health_score"],
        "cleaned_health_score": cleaned_audit["health_score"],
        "health_score_delta": round(cleaned_audit["health_score"] - raw_audit["health_score"], 1),
        "initial_rows": raw_audit["total_rows"],
        "cleaned_rows": cleaned_audit["total_rows"],
        "initial_cols": raw_audit["total_cols"],
        "cleaned_cols": cleaned_audit["total_cols"],
        "initial_missing_cells": raw_audit["total_missing_cells"],
        "cleaned_missing_cells": cleaned_audit["total_missing_cells"],
        "duplicates_removed": raw_audit["duplicate_rows"],
        "outliers_treated": treated_outliers_count,
        "transform_log": transform_log,
        "raw_columns": raw_audit["columns"],
        "cleaned_columns": cleaned_audit["columns"]
    }

    # Generate reproducible Python script
    python_script = generate_cleaning_script(df, config)

    return clean_df, audit_report, python_script


def generate_cleaning_script(raw_df: pd.DataFrame, config: Dict[str, Any]) -> str:
    """
    Generates a clean, reproducible Python script containing the entire cleaning pipeline.
    """
    script = f'''"""
AutoAnalyst Pro - Automated Cleaning & Preprocessing Pipeline
Generated automatically by Multi-Purpose Analytica Engine.
"""

import re
import numpy as np
import pandas as pd

def run_cleaning_pipeline(file_path_or_df):
    # 1. Load Data
    if isinstance(file_path_or_df, str):
        df = pd.read_csv(file_path_or_df)
    else:
        df = file_path_or_df.copy()

    print(f"Initial shape: {{df.shape}}")

    # 2. Purge Duplicates
    df = df.drop_duplicates().reset_index(drop=True)
    print(f"Shape after deduplication: {{df.shape}}")

    # 3. Standardize Implicit Nulls
    implicit_nulls = {repr(list(IMPLICIT_NULL_STRINGS)[:12])}
    for col in df.select_dtypes(include=[object, "string"]).columns:
        df[col] = df[col].astype(str).str.strip()
        df.loc[df[col].str.lower().isin(implicit_nulls), col] = np.nan

    # 4. Clean Dirty Numeric Strings (currencies, commas, units)
    for col in df.select_dtypes(include=[object, "string"]).columns:
        sample = df[col].dropna().astype(str)
        if len(sample) > 0:
            cleaned = sample.str.replace(r"[\\$,€£¥%]", "", regex=True)
            cleaned = cleaned.str.replace(r"\\b(usd|eur|gbp|sqft|sq\\s*ft|mg/dl|kg|lbs|mmhg)\\b", "", case=False, regex=True).str.strip()
            num_ratio = pd.to_numeric(cleaned, errors="coerce").notna().sum() / len(sample)
            if num_ratio > 0.70:
                df[col] = pd.to_numeric(
                    df[col].astype(str).str.replace(r"[\\$,€£¥%]", "", regex=True)
                    .str.replace(r"\\b(usd|eur|gbp|sqft|sq\\s*ft|mg/dl|kg|lbs|mmhg)\\b", "", case=False, regex=True)
                    .str.strip(),
                    errors="coerce"
                )

    # 5. Parse Mixed Datetimes & Extract Features
    for col in df.select_dtypes(include=[object, "string"]).columns:
        try:
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            if (parsed.notna().sum() / max(1, len(df))) > 0.60:
                df[col] = parsed
                df[f"{{col}}_Year"] = df[col].dt.year
                df[f"{{col}}_Month"] = df[col].dt.month
                df[f"{{col}}_DayOfWeek"] = df[col].dt.day_name()
                df[f"{{col}}_IsWeekend"] = df[col].dt.dayofweek.isin([5, 6]).astype(int)
        except Exception:
            pass

    # 6. Normalize Text Casing & Whitespace
    for col in df.select_dtypes(include=[object, "string"]).columns:
        df[col] = df[col].astype(str).str.strip().str.replace(r"\\s+", " ", regex=True)
        if df[col].nunique() < len(df) * 0.5:
            df[col] = df[col].str.title()

    # 7. Treat Extreme Outliers (Winsorization)
    num_cols = df.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        if not col.endswith(("_Year", "_IsWeekend")) and "id" not in col.lower() and df[col].nunique() > 4:
            p01 = df[col].quantile(0.01)
            p99 = df[col].quantile(0.99)
            df[col] = df[col].clip(lower=p01, upper=p99)

    # 8. Impute Missing Values (Median for numerics, Mode for categoricals)
    for col in df.select_dtypes(include=[np.number]).columns:
        if df[col].isna().any():
            df[col] = df[col].fillna(df[col].median())

    for col in df.select_dtypes(include=[object, "string"]).columns:
        if df[col].isna().any():
            mode_val = df[col].mode().iloc[0] if len(df[col].mode()) > 0 else "Unknown"
            df[col] = df[col].fillna(mode_val)

    print(f"Final Cleaned Dataset Shape: {{df.shape}}")
    return df

if __name__ == "__main__":
    import sys
    input_file = sys.argv[1] if len(sys.argv) > 1 else "data.csv"
    cleaned = run_cleaning_pipeline(input_file)
    cleaned.to_csv("cleaned_output.csv", index=False)
    print("Cleaned data saved to cleaned_output.csv")
'''
    return script
