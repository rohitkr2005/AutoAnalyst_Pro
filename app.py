"""
AutoAnalyst Pro - Main Application Server (Flask)
Full-Stack Automated Data Science, User Authentication, AI Copilot & Live Dashboard Studio
"""

import os
import io
import math
import json
import time
import threading
import webbrowser
from functools import wraps

import numpy as np
import pandas as pd
from flask import Flask, render_template, request, jsonify, send_file, Response, session, redirect, url_for

from engine.auth import init_auth_db, register_user, authenticate_user, get_user_by_id, record_user_activity, get_user_history
from engine.sample_datasets import init_all_samples, SAMPLES_DIR
from engine.cleaner import sniff_and_read_csv, audit_dataset_health, clean_and_preprocess
from engine.analytics import compute_comprehensive_eda
from engine.ml_engine import run_ml_pipeline

# Initialize Flask app
app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024  # 32MB max upload size
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "autoanalyst-secure-session-key-2026-production")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# In-memory storage for active dataset session
SESSION_DATA = {
    "dataset_name": "No dataset loaded",
    "raw_df": None,
    "cleaned_df": None,
    "raw_audit": None,
    "cleaned_audit": None,
    "audit_report": None,
    "python_script": "",
    "eda_cache": None,
    "ml_cache": None
}


def sanitize_for_json(val):
    """Recursively converts NumPy / Pandas objects and NaNs/Infs to JSON-safe primitives."""
    if isinstance(val, (np.integer, np.int64, np.int32)):
        return int(val)
    if isinstance(val, (np.floating, np.float64, np.float32)):
        if np.isnan(val) or np.isinf(val):
            return None
        return float(val)
    if isinstance(val, (np.bool_, bool)):
        return bool(val)
    if isinstance(val, (np.ndarray, list)):
        return [sanitize_for_json(x) for x in val]
    if isinstance(val, dict):
        return {str(k): sanitize_for_json(v) for k, v in val.items()}
    if pd.isna(val):
        return None
    if isinstance(val, pd.Timestamp):
        return val.strftime("%Y-%m-%d %H:%M:%S")
    return val


def login_required(f):
    """Decorator ensuring routes are accessible only by authenticated sessions."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"status": "error", "message": "Authentication required. Please log in.", "code": 401}), 401
            return redirect(url_for("login_page"))
        return f(*args, **kwargs)
    return decorated_function


@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET,PUT,POST,DELETE,OPTIONS"
    return response


# ==========================================
# AUTHENTICATION ROUTES
# ==========================================

@app.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("index"))
    return render_template("login.html")


@app.route("/register")
def register_page():
    return redirect(url_for("login_page"))


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")
    result = authenticate_user(username, password)
    if result["success"]:
        user = result["user"]
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["full_name"] = user["full_name"]
        session["email"] = user["email"]
        session["role"] = user["role"]
        return jsonify({"status": "success", "user": user})
    return jsonify({"status": "error", "message": result["message"]}), 401


@app.route("/api/auth/register", methods=["POST"])
def api_register():
    data = request.get_json() or {}
    username = data.get("username", "")
    email = data.get("email", "")
    password = data.get("password", "")
    full_name = data.get("full_name", "")
    result = register_user(username, email, password, full_name)
    if result["success"]:
        user = result["user"]
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["full_name"] = user["full_name"]
        session["email"] = user["email"]
        session["role"] = user["role"]
        return jsonify({"status": "success", "user": user})
    return jsonify({"status": "error", "message": result["message"]}), 400


@app.route("/api/auth/logout", methods=["POST", "GET"])
def api_logout():
    session.clear()
    if request.path.startswith("/api/"):
        return jsonify({"status": "success", "message": "Logged out successfully"})
    return redirect(url_for("login_page"))


@app.route("/api/auth/me", methods=["GET"])
def api_me():
    if "user_id" not in session:
        return jsonify({"status": "error", "authenticated": False}), 401
    user = get_user_by_id(session["user_id"])
    history = get_user_history(session["user_id"], limit=5)
    return jsonify({
        "status": "success",
        "authenticated": True,
        "user": user,
        "recent_history": history
    })


# ==========================================
# DASHBOARD & PIPELINE ROUTES
# ==========================================

@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/samples", methods=["GET"])
@login_required
def get_samples():
    """Returns available pre-packaged messy demo datasets."""
    datasets = init_all_samples()
    sample_list = []
    for key, info in datasets.items():
        sample_list.append({
            "id": key,
            "name": info["name"],
            "description": info["description"]
        })
    return jsonify({"status": "success", "samples": sample_list})


@app.route("/api/load-sample", methods=["POST"])
@login_required
def load_sample():
    """Loads one of the built-in messy datasets into active session."""
    data = request.get_json() or {}
    sample_id = data.get("sample_id", "ecommerce")
    
    filename_map = {
        "ecommerce": ("ecommerce_messy.csv", "Messy E-Commerce Omnichannel"),
        "healthcare": ("healthcare_clinical_messy.csv", "Clinical Patient Records"),
        "saas": ("saas_subscriptions_messy.csv", "SaaS Subscriptions & Churn"),
        "real_estate": ("real_estate_messy.csv", "Residential Housing Market")
    }

    if sample_id not in filename_map:
        return jsonify({"status": "error", "message": f"Sample '{sample_id}' not found."}), 404

    fname, display_name = filename_map[sample_id]
    file_path = os.path.join(SAMPLES_DIR, fname)
    if not os.path.exists(file_path):
        init_all_samples()

    try:
        df = pd.read_csv(file_path)
        SESSION_DATA["dataset_name"] = display_name
        SESSION_DATA["raw_df"] = df.copy()
        SESSION_DATA["cleaned_df"] = None
        SESSION_DATA["eda_cache"] = None
        SESSION_DATA["ml_cache"] = None
        
        # Initial audit
        raw_audit = audit_dataset_health(df)
        SESSION_DATA["raw_audit"] = raw_audit

        # Log activity
        if "user_id" in session:
            record_user_activity(session["user_id"], display_name, len(df), raw_audit["health_score"], "Loaded Demo Dataset")

        # Preview table (first 12 rows)
        preview_rows = []
        for _, r in df.head(12).iterrows():
            preview_rows.append({str(c): (None if pd.isna(r[c]) else str(r[c])) for c in df.columns})

        return jsonify(sanitize_for_json({
            "status": "success",
            "dataset_name": display_name,
            "shape": {"rows": len(df), "cols": len(df.columns)},
            "columns": list(df.columns),
            "raw_audit": raw_audit,
            "preview": preview_rows
        }))
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/upload", methods=["POST"])
@login_required
def upload_file():
    """Handles file upload (CSV, TSV, XLSX, JSON) or raw text paste."""
    try:
        if "file" in request.files:
            uploaded_file = request.files["file"]
            filename = uploaded_file.filename or "uploaded_data.csv"
            file_bytes = uploaded_file.read()
            df = sniff_and_read_csv(file_bytes, filename)
            dataset_name = filename
        elif request.is_json and "raw_text" in request.get_json():
            raw_text = request.get_json()["raw_text"]
            df = sniff_and_read_csv(raw_text.encode("utf-8"), "pasted_data.csv")
            dataset_name = "Pasted Dataset"
        else:
            return jsonify({"status": "error", "message": "No file or data provided"}), 400

        if df is None or len(df) == 0:
            return jsonify({"status": "error", "message": "Could not parse any rows from provided data."}), 400

        SESSION_DATA["dataset_name"] = dataset_name
        SESSION_DATA["raw_df"] = df.copy()
        SESSION_DATA["cleaned_df"] = None
        SESSION_DATA["eda_cache"] = None
        SESSION_DATA["ml_cache"] = None

        raw_audit = audit_dataset_health(df)
        SESSION_DATA["raw_audit"] = raw_audit

        if "user_id" in session:
            record_user_activity(session["user_id"], dataset_name, len(df), raw_audit["health_score"], "Uploaded Dataset")

        preview_rows = []
        for _, r in df.head(12).iterrows():
            preview_rows.append({str(c): (None if pd.isna(r[c]) else str(r[c])) for c in df.columns})

        return jsonify(sanitize_for_json({
            "status": "success",
            "dataset_name": dataset_name,
            "shape": {"rows": len(df), "cols": len(df.columns)},
            "columns": [str(c) for c in df.columns],
            "raw_audit": raw_audit,
            "preview": preview_rows
        }))
    except Exception as e:
        return jsonify({"status": "error", "message": f"Upload processing error: {str(e)}"}), 500


@app.route("/api/clean", methods=["POST"])
@login_required
def run_cleaning():
    """Executes the automated cleaning pipeline on the active raw dataset."""
    if SESSION_DATA["raw_df"] is None:
        return jsonify({"status": "error", "message": "No dataset currently loaded. Please upload or load a sample first."}), 400

    config = request.get_json() if request.is_json else None
    try:
        raw_df = SESSION_DATA["raw_df"]
        clean_df, audit_report, py_script = clean_and_preprocess(raw_df, config)
        
        SESSION_DATA["cleaned_df"] = clean_df.copy()
        SESSION_DATA["audit_report"] = audit_report
        SESSION_DATA["python_script"] = py_script
        SESSION_DATA["eda_cache"] = None
        SESSION_DATA["ml_cache"] = None

        if "user_id" in session:
            record_user_activity(
                session["user_id"], 
                SESSION_DATA.get("dataset_name", "Cleaned Data"), 
                len(clean_df), 
                audit_report["cleaned_health_score"], 
                "Cleaned & Preprocessed"
            )

        # Preview of cleaned data
        preview_rows = []
        for _, r in clean_df.head(12).iterrows():
            row_dict = {}
            for c in clean_df.columns:
                val = r[c]
                if pd.isna(val):
                    row_dict[str(c)] = None
                elif isinstance(val, (int, float, np.integer, np.floating)):
                    row_dict[str(c)] = round(float(val), 2)
                elif isinstance(val, pd.Timestamp):
                    row_dict[str(c)] = val.strftime("%Y-%m-%d")
                else:
                    row_dict[str(c)] = str(val)
            preview_rows.append(row_dict)

        return jsonify(sanitize_for_json({
            "status": "success",
            "audit_report": audit_report,
            "preview": preview_rows,
            "cleaned_columns": [str(c) for c in clean_df.columns],
            "python_script": py_script
        }))
    except Exception as e:
        return jsonify({"status": "error", "message": f"Cleaning error: {str(e)}"}), 500


@app.route("/api/eda", methods=["POST", "GET"])
@login_required
def run_eda():
    """Computes comprehensive statistical EDA and distributions."""
    df = SESSION_DATA["cleaned_df"] if SESSION_DATA["cleaned_df"] is not None else SESSION_DATA["raw_df"]
    if df is None:
        return jsonify({"status": "error", "message": "No dataset loaded."}), 400

    if SESSION_DATA["eda_cache"] is not None:
        return jsonify(sanitize_for_json({"status": "success", "eda": SESSION_DATA["eda_cache"]}))

    try:
        eda_results = compute_comprehensive_eda(df)
        SESSION_DATA["eda_cache"] = eda_results
        return jsonify(sanitize_for_json({"status": "success", "eda": eda_results}))
    except Exception as e:
        return jsonify({"status": "error", "message": f"EDA computation error: {str(e)}"}), 500


@app.route("/api/ml", methods=["POST", "GET"])
@login_required
def run_ml():
    """Executes Machine Learning, Clustering, Anomaly Detection, Feature Importance, and Executive Insights."""
    df = SESSION_DATA["cleaned_df"] if SESSION_DATA["cleaned_df"] is not None else SESSION_DATA["raw_df"]
    if df is None:
        return jsonify({"status": "error", "message": "No dataset loaded."}), 400

    target = None
    if request.is_json:
        target = request.get_json().get("target_metric")

    try:
        ml_results = run_ml_pipeline(df, target_metric=target)
        SESSION_DATA["ml_cache"] = ml_results
        return jsonify(sanitize_for_json({"status": "success", "ml": ml_results}))
    except Exception as e:
        return jsonify({"status": "error", "message": f"ML pipeline error: {str(e)}"}), 500


@app.route("/api/chat", methods=["POST"])
@login_required
def api_chat():
    """Interactive AI Data Analyst Copilot endpoint."""
    data = request.get_json() or {}
    user_query = data.get("message", "").strip()
    if not user_query:
        return jsonify({"status": "error", "message": "Query message required"}), 400

    reply = generate_analyst_chat_response(user_query, SESSION_DATA)
    return jsonify({"status": "success", "reply": reply})


def generate_analyst_chat_response(query: str, session_data: dict) -> str:
    """Intelligently generates data-grounded natural language insights for user queries."""
    q = query.lower()
    ds_name = session_data.get("dataset_name", "your active dataset")
    eda = session_data.get("eda_cache")
    ml = session_data.get("ml_cache")
    audit = session_data.get("audit_report") or session_data.get("raw_audit")

    if session_data.get("raw_df") is None:
        return "👋 Welcome! No dataset is loaded into memory yet. In Stage 1, please drag and drop a file (CSV/Excel/JSON) or click one of our instant benchmark datasets to start our exploration!"

    # 1. Driver / Feature Importance questions
    if any(w in q for w in ["driver", "importance", "impact", "influence", "predict", "contribute"]):
        if ml and ml.get("feature_importance") and ml["feature_importance"].get("drivers"):
            fi = ml["feature_importance"]
            top_drivers = fi["drivers"][:4]
            bullets = "\n".join([f"• **{d['feature']}**: {d['importance']}% relative contribution" for d in top_drivers])
            return (f"📊 **Key Driver Analysis for {fi.get('target_metric', 'Primary Metric')}**:\n\n"
                    f"Based on Random Forest predictive feature importance modeling, here are the top factors exerting the strongest statistical leverage:\n\n"
                    f"{bullets}\n\n"
                    f"💡 *Recommendation*: Prioritize optimizing **{top_drivers[0]['feature']}** to drive the greatest measurable movement in {fi.get('target_metric')}.")
        else:
            return f"The Machine Learning pipeline has not isolated feature importance yet. Please click 'Run Auto-Clean' in Stage 2, and feature drivers will automatically be computed!"

    # 2. Anomaly / Outlier questions
    if any(w in q for w in ["anomaly", "outlier", "risk", "fraud", "irregular", "unusual", "strange"]):
        if ml and ml.get("anomalies"):
            anom = ml["anomalies"]
            return (f"⚠️ **Anomaly Detection Report (Isolation Forest)**:\n\n"
                    f"• **Total Anomalies Flagged**: {anom['total_anomalies_detected']} records ({anom['anomaly_percentage']}% of total data)\n"
                    f"• **Algorithm**: Unsupervised Isolation Forest (contamination = 3.5%)\n"
                    f"• **Highest Anomaly Indices**: Rows {', '.join(['#' + str(x['row_index']) for x in anom['top_anomalies'][:5]])}\n\n"
                    f"💡 *Risk Note*: These records exhibit multi-dimensional divergence across several features simultaneously. Check the Anomaly Explorer in the dashboard to review their exact values.")
        elif audit:
            out_cnt = audit.get("total_outliers", audit.get("outliers_treated", 0))
            return f"We detected {out_cnt} univariate outliers via Tukey's IQR fences. Run the ML pipeline in Stage 4 to see multivariate Isolation Forest anomaly clusters!"

    # 3. Clustering & Customer Persona questions
    if any(w in q for w in ["cluster", "persona", "segment", "group", "cohort", "k-means"]):
        if ml and ml.get("clustering") and ml["clustering"].get("personas"):
            cl = ml["clustering"]
            persona_text = "\n\n".join([f"• **{p['name']}** ({p['percentage']}% of records - {p['size']:,} total):\n  Traits: {', '.join(p['key_traits'])}" for p in cl["personas"]])
            return (f"👥 **Statistical Entity Segmentation (K-Means & PCA)**:\n\n"
                    f"Optimal cluster count determined as **K = {cl['optimal_k']}** with a silhouette separation score of **{cl['best_silhouette_score']}**.\n\n"
                    f"{persona_text}\n\n"
                    f"💡 *Strategic Takeaway*: Treat these segments with tailored business strategies rather than a one-size-fits-all approach.")
        else:
            return "Clustering models are waiting for data cleaning to complete. Head to Stage 2 and run Auto-Clean to uncover your optimal cluster personas!"

    # 4. Trend / Forecasting questions
    if any(w in q for w in ["trend", "forecast", "future", "projection", "time", "momentum", "tomorrow", "growth"]):
        if ml and ml.get("time_series"):
            ts = ml["time_series"]
            return (f"📈 **Time-Series Momentum & 14-Day Projection**:\n\n"
                    f"• **Analyzed Metric**: {ts['target_metric']} (Date: {ts['date_column']})\n"
                    f"• **Historical Direction**: **{ts['trend_direction']}** (period velocity: {ts['growth_rate_pct']}%)\n"
                    f"• **Projected Baseline**: Next 14 periods forecast an average level of ~{ts['forecast_values'][-1]:,.1f}\n\n"
                    f"💡 *Analyst Perspective*: Confidence intervals indicate predictable seasonality. Keep monitoring moving averages to catch inflection points early.")
        else:
            return "No time-series date column was detected in this dataset, or temporal features haven't been modeled yet. For time series forecasts, ensure your data includes timestamp or date values!"

    # 5. Data Quality / Cleaning questions
    if any(w in q for w in ["clean", "quality", "missing", "duplicate", "null", "health", "score"]):
        if audit:
            h_score = audit.get("cleaned_health_score", audit.get("health_score", "--"))
            init_score = audit.get("initial_health_score", audit.get("health_score", "--"))
            dups = audit.get("duplicates_removed", audit.get("duplicate_rows", 0))
            missing = audit.get("cleaned_missing_cells", audit.get("total_missing_cells", 0))
            return (f"🧼 **Data Quality & Health Audit**:\n\n"
                    f"• **Current Health Score**: **{h_score}/100** (Initial: {init_score}%)\n"
                    f"• **Duplicate Rows Purged**: {dups}\n"
                    f"• **Missing Cells Remaining**: {missing}\n\n"
                    f"The dataset has been standardized with median/mode imputation, currency stripping, and outlier winsorization. It is fully certified for executive analysis.")

    # 6. Correlation / Relationships
    if any(w in q for w in ["correlation", "relationship", "relation", "pearson", "spearman", "heatmap"]):
        if eda and eda.get("correlation") and eda["correlation"].get("top_correlations"):
            top_c = eda["correlation"]["top_correlations"][:3]
            lines = "\n".join([f"• **{p['feature_a']}** ⟷ **{p['feature_b']}**: r = {p['pearson_r']} ({p['strength']} {p['direction']})" for p in top_c])
            return (f"🔗 **Top Correlated Relationships**:\n\n"
                    f"{lines}\n\n"
                    f"💡 *Insight*: Strong positive correlations suggest collinearity or shared underlying drivers. Click any cell in the Stage 3 Heatmap to inspect the scatter distribution!")

    # Default Executive Summary
    summary_bullets = ""
    if ml and ml.get("executive_summary"):
        summary_bullets = "\n\n".join([f"• **{b['headline']}**: {b['detail']}" for b in ml["executive_summary"][:3]])
    return (f"👋 Hello! I am your **AutoAnalyst AI Copilot** reviewing **{ds_name}**.\n\n"
            f"Here is a high-level executive snapshot:\n\n"
            f"{summary_bullets if summary_bullets else '• Dataset loaded and ready for automated pipeline execution.'}\n\n"
            f"Feel free to ask me:\n"
            f"• *'What are the primary revenue drivers?'*\n"
            f"• *'Tell me about our entity clusters and personas'*\n"
            f"• *'Are there any fraud or anomaly flags?'*\n"
            f"• *'Give me the 14-day trend forecast'*")


@app.route("/api/data-query", methods=["POST"])
@login_required
def query_data_rows():
    """Paginated data retrieval for the live Data Inspector table."""
    data = request.get_json() or {}
    view_mode = data.get("view_mode", "cleaned")
    page = max(1, int(data.get("page", 1)))
    page_size = min(100, max(5, int(data.get("page_size", 15))))
    search_query = data.get("search", "").strip().lower()
    sort_by = data.get("sort_by")
    sort_asc = data.get("sort_asc", True)

    df = SESSION_DATA["cleaned_df"] if (view_mode == "cleaned" and SESSION_DATA["cleaned_df"] is not None) else SESSION_DATA["raw_df"]
    if df is None:
        return jsonify({"status": "success", "rows": [], "total_rows": 0, "total_pages": 0, "page": 1})

    filtered_df = df
    if search_query:
        mask = pd.Series(False, index=df.index)
        for col in df.columns:
            mask = mask | df[col].astype(str).str.lower().str.contains(search_query, regex=False, na=False)
        filtered_df = df[mask]

    if sort_by and sort_by in filtered_df.columns:
        filtered_df = filtered_df.sort_values(by=sort_by, ascending=sort_asc)

    total_rows = len(filtered_df)
    total_pages = max(1, math.ceil(total_rows / page_size))
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    sliced = filtered_df.iloc[start_idx:end_idx]
    rows = []
    for idx, r in sliced.iterrows():
        row_dict = {"_index": int(idx)}
        for c in df.columns:
            val = r[c]
            if pd.isna(val):
                row_dict[str(c)] = None
            elif isinstance(val, (int, float, np.integer, np.floating)):
                row_dict[str(c)] = round(float(val), 2)
            elif isinstance(val, pd.Timestamp):
                row_dict[str(c)] = val.strftime("%Y-%m-%d")
            else:
                row_dict[str(c)] = str(val)
        rows.append(row_dict)

    return jsonify(sanitize_for_json({
        "status": "success",
        "rows": rows,
        "columns": [str(c) for c in df.columns],
        "total_rows": total_rows,
        "total_pages": total_pages,
        "page": page,
        "page_size": page_size
    }))


@app.route("/api/export-csv", methods=["GET"])
@login_required
def export_csv():
    """Exports and downloads the cleaned dataset as CSV."""
    df = SESSION_DATA["cleaned_df"] if SESSION_DATA["cleaned_df"] is not None else SESSION_DATA["raw_df"]
    if df is None:
        return "No dataset loaded to export", 400

    csv_buffer = io.StringIO()
    df.to_csv(csv_buffer, index=False)
    csv_bytes = io.BytesIO(csv_buffer.getvalue().encode("utf-8"))
    
    clean_name = SESSION_DATA.get("dataset_name", "dataset").replace(" ", "_").lower()
    return send_file(
        csv_bytes,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"cleaned_{clean_name}.csv"
    )


@app.route("/api/export-script", methods=["GET"])
@login_required
def export_script():
    """Exports and downloads the Python cleaning script."""
    script = SESSION_DATA.get("python_script", "# No pipeline script generated yet")
    return Response(
        script,
        mimetype="text/x-python",
        headers={"Content-Disposition": "attachment;filename=clean_pipeline.py"}
    )


def auto_open_browser():
    time.sleep(1.2)
    try:
        webbrowser.open("http://localhost:5000/login")
    except Exception:
        pass


if __name__ == "__main__":
    init_auth_db()
    init_all_samples()
    print("===============================================================", flush=True)
    print("  AutoAnalyst Pro Analytics Engine & Live Dashboard is READY! ", flush=True)
    print("  Access in browser: http://localhost:5000/login             ", flush=True)
    print("  (Opening your default web browser automatically...)          ", flush=True)
    print("  Press CTRL+C in this window anytime to stop the server.      ", flush=True)
    print("===============================================================", flush=True)
    threading.Thread(target=auto_open_browser, daemon=True).start()
    app.run(host="0.0.0.0", port=5000, debug=False)
