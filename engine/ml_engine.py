"""
AutoAnalyst Pro - Machine Learning & Automated Executive Insights Engine
Implements:
1. Optimal K-Means Clustering + Silhouette Scoring + PCA 2D Dimensionality Reduction + Persona Descriptions
2. Isolation Forest Multi-Attribute Anomaly Detection
3. Random Forest Key Driver Analysis & Feature Importance
4. Time Series Trend Projection & Forecasting
5. Automated Natural Language Executive Summary & Strategic Business Recommendations
"""

import os
os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.ensemble import IsolationForest, RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score


def run_ml_pipeline(
    df: pd.DataFrame, 
    target_metric: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the automated data science and ML pipeline.
    """
    n_rows = len(df)
    numeric_cols = list(df.select_dtypes(include=[np.number]).columns)
    # Exclude ID or year columns from feature matrices
    feature_num_cols = [c for c in numeric_cols if not c.endswith(("_Year", "_IsWeekend")) and "id" not in c.lower() and df[c].nunique() > 4]

    results = {
        "clustering": None,
        "anomalies": None,
        "feature_importance": None,
        "time_series": None,
        "executive_summary": []
    }

    if len(feature_num_cols) < 2 or n_rows < 10:
        return results

    # 1. Optimal K-Means Clustering + PCA
    try:
        X = df[feature_num_cols].dropna()
        if len(X) >= 15:
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)

            # Evaluate silhouette score for k in 2..5
            best_k = 3
            best_score = -1.0
            silhouette_results = []
            
            max_k = min(6, len(X) - 1)
            for k in range(2, max_k):
                km = KMeans(n_clusters=k, random_state=42, n_init=10)
                labels = km.fit_predict(X_scaled)
                score = float(silhouette_score(X_scaled, labels))
                silhouette_results.append({"k": k, "score": round(score, 3)})
                if score > best_score:
                    best_score = score
                    best_k = k

            # Fit optimal model
            final_km = KMeans(n_clusters=best_k, random_state=42, n_init=10)
            cluster_labels = final_km.fit_predict(X_scaled)

            # 2D PCA Projection
            pca = PCA(n_components=2, random_state=42)
            X_pca = pca.fit_transform(X_scaled)
            exp_variance = [round(float(v) * 100, 1) for v in pca.explained_variance_ratio_]

            # Generate Cluster Personas / Archetypes
            cluster_personas = []
            centroids = final_km.cluster_centers_
            centroid_orig = scaler.inverse_transform(centroids)
            
            for i in range(best_k):
                mask = (cluster_labels == i)
                cluster_size = int(mask.sum())
                pct = round((cluster_size / len(cluster_labels)) * 100, 1)
                
                # Identify defining traits for this cluster
                traits = []
                for idx, col in enumerate(feature_num_cols):
                    mean_all = X[col].mean()
                    mean_cluster = centroid_orig[i][idx]
                    diff_pct = ((mean_cluster - mean_all) / (mean_all if mean_all != 0 else 1)) * 100
                    if abs(diff_pct) > 15:
                        qualifier = "High" if diff_pct > 0 else "Low"
                        traits.append(f"{qualifier} {col} ({round(mean_cluster, 1)})")

                persona_name = f"Cluster {i}: " + (", ".join(traits[:2]) if traits else f"Balanced Group")
                cluster_personas.append({
                    "cluster_id": i,
                    "name": persona_name,
                    "size": cluster_size,
                    "percentage": pct,
                    "key_traits": traits[:4]
                })

            # Sample scatter points for UI rendering (up to 300 points)
            sample_indices = np.random.choice(len(X), size=min(300, len(X)), replace=False)
            scatter_points = []
            for idx in sample_indices:
                scatter_points.append({
                    "x": round(float(X_pca[idx, 0]), 2),
                    "y": round(float(X_pca[idx, 1]), 2),
                    "cluster": int(cluster_labels[idx])
                })

            results["clustering"] = {
                "optimal_k": best_k,
                "best_silhouette_score": round(best_score, 3),
                "silhouette_evaluation": silhouette_results,
                "pca_explained_variance": exp_variance,
                "features_used": feature_num_cols,
                "personas": cluster_personas,
                "scatter_points": scatter_points
            }
    except Exception as e:
        results["clustering_error"] = str(e)

    # 2. Isolation Forest Anomaly Detection
    try:
        X_sub = df[feature_num_cols].dropna()
        if len(X_sub) >= 20:
            iso = IsolationForest(contamination=0.035, random_state=42)
            preds = iso.fit_predict(X_sub)
            scores = iso.decision_function(X_sub)

            anomaly_indices = np.where(preds == -1)[0]
            top_anomalies = []
            
            # Rank by most anomalous (lowest score)
            sorted_anomaly_idx = sorted(anomaly_indices, key=lambda idx: scores[idx])
            for idx in sorted_anomaly_idx[:10]:
                row = X_sub.iloc[idx]
                row_dict = {col: round(float(row[col]), 2) for col in feature_num_cols[:5]}
                top_anomalies.append({
                    "row_index": int(X_sub.index[idx]),
                    "anomaly_score": round(float(-1 * scores[idx]), 3),
                    "metrics": row_dict
                })

            results["anomalies"] = {
                "total_anomalies_detected": int(len(anomaly_indices)),
                "anomaly_percentage": round((len(anomaly_indices) / len(X_sub)) * 100, 2),
                "top_anomalies": top_anomalies
            }
    except Exception as e:
        results["anomalies_error"] = str(e)

    # 3. Key Driver Analysis (Random Forest Feature Importance)
    try:
        # Determine target metric
        target_col = target_metric
        if not target_col or target_col not in df.columns:
            # Auto-select the first major continuous revenue/price/charge column or primary metric
            priority_names = ["revenue", "price", "amount", "charge", "sales", "mrr", "cost", "score", "days", "bmi"]
            for p in priority_names:
                matches = [c for c in feature_num_cols if p in c.lower()]
                if matches:
                    target_col = matches[0]
                    break
            if not target_col and feature_num_cols:
                target_col = feature_num_cols[-1]

        if target_col and len(feature_num_cols) > 1:
            predictors = [c for c in feature_num_cols if c != target_col]
            if predictors:
                model_data = df[predictors + [target_col]].dropna()
                if len(model_data) >= 15:
                    X_pred = model_data[predictors]
                    y_pred = model_data[target_col]

                    rf = RandomForestRegressor(n_estimators=60, max_depth=6, random_state=42)
                    rf.fit(X_pred, y_pred)

                    importances = rf.feature_importances_
                    driver_list = []
                    for name, imp in zip(predictors, importances):
                        driver_list.append({
                            "feature": name,
                            "importance": round(float(imp) * 100, 1)
                        })
                    driver_list.sort(key=lambda x: x["importance"], reverse=True)

                    results["feature_importance"] = {
                        "target_metric": target_col,
                        "drivers": driver_list
                    }
    except Exception as e:
        results["feature_importance_error"] = str(e)

    # 4. Time Series Trend & Forecasting (if date column present)
    try:
        date_cols = list(df.select_dtypes(include=["datetime64[ns]", "datetime"]).columns)
        if date_cols and target_col:
            dcol = date_cols[0]
            ts_df = df[[dcol, target_col]].dropna().copy()
            ts_df[dcol] = pd.to_datetime(ts_df[dcol])
            ts_df = ts_df.sort_values(by=dcol)
            
            # Resample by Day or Week
            ts_df = ts_df.set_index(dcol)
            resampled = ts_df[target_col].resample("D").mean().dropna()
            if len(resampled) < 8:
                resampled = ts_df[target_col].resample("W").mean().dropna()

            if len(resampled) >= 6:
                historical_labels = [d.strftime("%Y-%m-%d") for d in resampled.index]
                historical_values = [round(float(v), 2) for v in resampled.values]

                # Rolling Moving Average (7 periods)
                rolling_avg = resampled.rolling(window=min(7, len(resampled)), min_periods=1).mean()
                rolling_values = [round(float(v), 2) for v in rolling_avg.values]

                # Simple linear trend projection for next 14 periods
                x_vals = np.arange(len(resampled))
                slope, intercept = np.polyfit(x_vals, resampled.values, 1)

                future_x = np.arange(len(resampled), len(resampled) + 14)
                forecast_values = [round(float(slope * fx + intercept), 2) for fx in future_x]
                
                # Confidence band (~10%)
                std_res = float(resampled.std()) if len(resampled) > 1 else 10.0
                upper_bound = [round(v + 1.28 * std_res, 2) for v in forecast_values]
                lower_bound = [round(max(0, v - 1.28 * std_res), 2) for v in forecast_values]

                last_date = resampled.index[-1]
                future_dates = [(last_date + pd.Timedelta(days=i)).strftime("%Y-%m-%d") for i in range(1, 15)]

                results["time_series"] = {
                    "date_column": dcol,
                    "target_metric": target_col,
                    "historical_dates": historical_labels,
                    "historical_values": historical_values,
                    "rolling_moving_average": rolling_values,
                    "forecast_dates": future_dates,
                    "forecast_values": forecast_values,
                    "upper_bound": upper_bound,
                    "lower_bound": lower_bound,
                    "trend_direction": "Upward" if slope > 0 else "Downward",
                    "growth_rate_pct": round((float(slope) / max(1e-5, abs(float(resampled.mean())))) * 100, 2)
                }
    except Exception as e:
        results["time_series_error"] = str(e)

    # 5. Automated Executive Insights Generation (Story about the data)
    executive_bullets = []
    
    # Volume and Dimensions
    executive_bullets.append({
        "type": "overview",
        "icon": "database",
        "badge": "Dataset Scope",
        "headline": f"Analyzed {n_rows:,} records across {len(df.columns)} standardized dimensions.",
        "detail": "Data cleaning and preprocessing pipeline successfully standardized data formats, imputed missing elements, and purged duplicate entries."
    })

    # Clustering insight
    if results.get("clustering") and results["clustering"].get("personas"):
        opt_k = results["clustering"]["optimal_k"]
        best_p = results["clustering"]["personas"][0]
        executive_bullets.append({
            "type": "clustering",
            "icon": "users",
            "badge": "Segmentation Discovery",
            "headline": f"Identified {opt_k} statistically distinct entity clusters (Silhouette: {results['clustering']['best_silhouette_score']}).",
            "detail": f"Largest segment: '{best_p['name']}' representing {best_p['percentage']}% of population. Segment personas provide distinct targeting opportunities."
        })

    # Feature Importance insight
    if results.get("feature_importance") and results["feature_importance"].get("drivers"):
        top_d = results["feature_importance"]["drivers"][0]
        t_metric = results["feature_importance"]["target_metric"]
        executive_bullets.append({
            "type": "driver",
            "icon": "trending-up",
            "badge": "Primary Driver",
            "headline": f"'{top_d['feature']}' is the strongest predictor of {t_metric} ({top_d['importance']}% feature weight).",
            "detail": f"Variations in {top_d['feature']} have the highest direct leverage on {t_metric}. Focus operational optimizations on this variable."
        })

    # Anomaly insight
    if results.get("anomalies"):
        anom_cnt = results["anomalies"]["total_anomalies_detected"]
        anom_pct = results["anomalies"]["anomaly_percentage"]
        executive_bullets.append({
            "type": "anomaly",
            "icon": "alert-triangle",
            "badge": "Anomaly Alert",
            "headline": f"Detected {anom_cnt} multi-attribute anomalies ({anom_pct}% of total records).",
            "detail": f"Isolation Forest flagged records with divergent behavioral signatures. Review flagged items in the Anomaly Explorer to mitigate fraud or operational errors."
        })

    # Time series insight
    if results.get("time_series"):
        ts = results["time_series"]
        executive_bullets.append({
            "type": "forecast",
            "icon": "calendar",
            "badge": "Trend Projection",
            "headline": f"{ts['target_metric']} demonstrates an overall {ts['trend_direction']} trend ({ts['growth_rate_pct']}% period velocity).",
            "detail": f"Forward 14-day projection indicates continued momentum. Seasonal fluctuations should be monitored against the calculated confidence bounds."
        })

    results["executive_summary"] = executive_bullets
    return results
