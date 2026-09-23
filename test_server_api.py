"""
Comprehensive automated API & pipeline test suite for AutoAnalyst Pro
"""
import requests
import json

BASE_URL = "http://127.0.0.1:5000"

def test_all():
    s = requests.Session()
    # Log in as demo analyst first
    login_res = s.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "Password123!"})
    assert login_res.status_code == 200, "Failed to authenticate test session"

    print("--- 1. Testing GET / (HTML Page) ---")
    r = s.get(f"{BASE_URL}/")
    assert r.status_code == 200
    assert "AutoAnalyst" in r.text
    print("GET / passed. Status:", r.status_code)

    print("\n--- 2. Testing GET /api/samples ---")
    r = s.get(f"{BASE_URL}/api/samples")
    assert r.status_code == 200
    samples = r.json()["samples"]
    assert len(samples) == 4
    print(f"GET /api/samples passed. Found {len(samples)} demo datasets.")

    print("\n--- 3. Testing POST /api/load-sample (ecommerce) ---")
    r = s.post(f"{BASE_URL}/api/load-sample", json={"sample_id": "ecommerce"})
    assert r.status_code == 200
    load_res = r.json()
    assert load_res["status"] == "success"
    raw_audit = load_res["raw_audit"]
    print(f"Raw Audit Health Score: {raw_audit['health_score']}/100, Rows: {load_res['shape']['rows']}, Cols: {load_res['shape']['cols']}")
    print(f"Detected Missing Cells: {raw_audit['total_missing_cells']}, Duplicates: {raw_audit['duplicate_rows']}")

    print("\n--- 4. Testing POST /api/clean ---")
    r = s.post(f"{BASE_URL}/api/clean", json={
        "remove_duplicates": True,
        "clean_dirty_numerics": True,
        "standardize_text": True,
        "parse_dates": True,
        "impute_missing": True,
        "treat_outliers": True
    })
    assert r.status_code == 200
    clean_res = r.json()
    assert clean_res["status"] == "success"
    rep = clean_res["audit_report"]
    print(f"Cleaned Health Score: {rep['cleaned_health_score']}/100 (+{rep['health_score_delta']}%)")
    print(f"Duplicates removed: {rep['duplicates_removed']}, Missing remaining: {rep['cleaned_missing_cells']}")
    print(f"Transformation logs logged: {len(rep['transform_log'])}")

    print("\n--- 5. Testing POST /api/eda ---")
    r = s.post(f"{BASE_URL}/api/eda")
    assert r.status_code == 200
    eda_res = r.json()["eda"]
    print(f"EDA computed: {len(eda_res['numeric_stats'])} numerical features, {len(eda_res['categorical_stats'])} categorical features")
    print(f"Correlation matrix size: {len(eda_res['correlation']['columns'])}x{len(eda_res['correlation']['columns'])}")
    print(f"Top correlation pairs: {len(eda_res['correlation']['top_correlations'])}")

    print("\n--- 6. Testing POST /api/ml ---")
    r = s.post(f"{BASE_URL}/api/ml")
    assert r.status_code == 200
    ml_res = r.json()["ml"]
    print(f"ML Clustering Optimal K: {ml_res['clustering']['optimal_k']} (Silhouette: {ml_res['clustering']['best_silhouette_score']})")
    print(f"Cluster personas: {[p['name'] for p in ml_res['clustering']['personas']]}")
    print(f"Isolation Forest Anomalies: {ml_res['anomalies']['total_anomalies_detected']} flagged ({ml_res['anomalies']['anomaly_percentage']}%)")
    print(f"Executive Summary Bullets: {len(ml_res['executive_summary'])}")

    print("\n--- 7. Testing POST /api/data-query (Data Inspector) ---")
    r = s.post(f"{BASE_URL}/api/data-query", json={"view_mode": "cleaned", "page": 1, "page_size": 5})
    assert r.status_code == 200
    dq = r.json()
    print(f"Data query returned {len(dq['rows'])} rows out of {dq['total_rows']} total rows, {dq['total_pages']} pages.")

    print("\n--- 8. Testing GET /api/export-csv ---")
    r = s.get(f"{BASE_URL}/api/export-csv")
    assert r.status_code == 200
    assert len(r.content) > 1000
    print(f"CSV Export verified: {len(r.content):,} bytes received.")

    print("\n--- 9. Testing GET /api/export-script ---")
    r = s.get(f"{BASE_URL}/api/export-script")
    assert r.status_code == 200
    assert "def run_cleaning_pipeline" in r.text
    print(f"Python Script Export verified: {len(r.text):,} characters received.")

    print("\n========================================================")
    print(" ALL 9 END-TO-END PIPELINE TESTS PASSED WITH 100% SUCCESS!")
    print("========================================================")

if __name__ == "__main__":
    test_all()
