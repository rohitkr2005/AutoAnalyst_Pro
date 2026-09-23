# ⚡ AutoAnalyst Pro - AI-Powered Analytics & BI Studio

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0%2B-black.svg?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Scikit-Learn](https://img.shields.io/badge/scikit--learn-1.3%2B-orange.svg?logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![Chart.js](https://img.shields.io/badge/Chart.js-4.4%2B-FF6384.svg?logo=chartdotjs&logoColor=white)](https://www.chartjs.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **AutoAnalyst Pro** is an autonomous data science and business intelligence platform designed to automate the complete workflow of a data analyst. From ingesting messy, raw tabular data to automated cleansing, statistical exploratory data analysis (EDA), machine learning modeling, and an interactive executive live dashboard—complete with an AI Copilot for conversational data intelligence.

---

## 🌟 Key Features

### 1. 🔄 End-to-End Automated Data Science Pipeline
- **Raw & Messy Data Ingestion**: Supports drag-and-drop CSV, TSV, XLSX, and JSON files, or 1-click loading from 4 built-in real-world messy benchmark datasets.
- **Smart Audit & Health Scoring**: Automatically scores data quality before and after cleaning across completeness, uniqueness, type consistency, and validity.

### 2. 🧹 Autonomous Data Cleansing & Preprocessing
- **Currency & Unit Stripping**: Detects and parses dirty formatted numbers (`$1,234.50`, `45kg`, `12%`).
- **Intelligent Imputation**: Missing values handled via automated median (numerical) and mode (categorical) imputation.
- **Outlier Winsorization**: Robust IQR-based outlier detection and boundary capping to preserve data integrity without arbitrary record dropping.
- **Multi-Format Date Parsing**: Resolves mixed datetime notations into ISO timestamps with feature extractions (day of week, month, quarter).
- **Automated Deduplication**: Exact and near-duplicate record pruning.

### 3. 📈 Exploratory Data Analysis & Statistical Profiling
- **Correlation Matrix**: Computes Pearson and Spearman coefficient matrices with automated detection of strong statistical couplings.
- **Distribution Analysis**: Calculates statistical moments (mean, median, standard deviation, skewness, kurtosis).
- **Categorical Frequency Breakdowns**: Automatic top-K cardinality profiling.

### 4. 🧠 Automated Machine Learning Lab
- **Entity Segmentation**: K-Means clustering with automated optimal $K$ detection via Silhouette scoring and 2D PCA dimensionality reduction.
- **Anomaly Detection**: Unsupervised Isolation Forest modeling with multi-dimensional divergence scoring and row-level risk flagging.
- **Feature Importance / Key Driver Analysis**: Random Forest ensemble modeling to identify which independent variables exert the strongest leverage on primary outcomes.
- **Time-Series Forecasting**: Moving-average trajectory projections with trend confidence intervals.

### 5. ✨ Conversational AI Copilot
- **Natural Language Data Querying**: Ask questions about your dataset in plain English and receive instant, grounded statistical interpretations, driver breakdowns, persona summaries, and anomaly alerts.

### 6. 🎨 3-Mode Theme System & Live 3D Perspective Canvas
- **3-Mode Theme Engine**: Seamless switching between **Light**, **Dark**, and **System/Device** theme with real-time OS preference change listening and anti-FOUC (Flash of Unstyled Content) initialization.
- **Live 3D Perspective Background**: Hardware-accelerated 60 FPS HTML5 canvas featuring:
  - 3D perspective projection $(X, Y, Z)$
  - Interactive mouse parallax tilt and rotational orbit
  - Floating 3D geometric wireframe polyhedra (data crystals)
  - Depth-attenuated filament connections and traveling data pulse packets
  - Battery-efficient auto-pause when the browser tab is inactive.

### 7. 🔐 User Authentication & Session Security
- User registration and login portal backed by SQLite and Werkzeug cryptographic password hashing.
- Role-based session tracking with demo 1-click access.

### 8. 📥 Comprehensive Export Suite
- **Cleaned Dataset**: Export sanitized, ready-to-model CSVs.
- **Reproducible Python Script**: Export a standalone, self-contained Python pipeline script (`clean_pipeline.py`) capturing all applied transformations.
- **Executive Report**: Print-ready, executive summary report with high-resolution charts.

---

## 🏗️ Architecture & Pipeline Flow

```
Raw & Messy Input (CSV / TSV / XLSX / JSON)
   │
   ▼
[Stage 1: Smart Ingestion & Quality Audit] ──> Calculates Initial Health Score
   │
   ▼
[Stage 2: Automated Cleaning Engine]       ──> Type Casts, Imputes, Winsorizes, Deduplicates
   │
   ▼
[Stage 3: Statistical EDA & Profiling]    ──> Correlation Matrix, Distributions, Skewness
   │
   ▼
[Stage 4: Automated Machine Learning]      ──> K-Means Clustering, PCA, Isolation Forest, Random Forest Drivers
   │
   ▼
[Stage 5: Live BI Dashboard & AI Copilot]  ──> Interactive Visual Canvas, Chat Copilot, Export Suite
```

---

## 🚀 Quick Start Guide

### Prerequisites
- Python 3.10 or higher
- `pip` (Python package manager)

### 1. Clone the Repository
```bash
git clone https://github.com/rohitkr2005/AutoAnalyst_Pro.git
cd AutoAnalyst_Pro
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Application
**On Windows:**
Double-click `run.bat` or run:
```bash
python app.py
```

**On macOS / Linux:**
```bash
python3 app.py
```

Open your browser and navigate to:
```
http://localhost:5000
```

---

## 🔑 Default Credentials

For quick evaluation, click the **"⚡ 1-Click Demo Analyst Sign In"** button on the login screen, or use:

| Field | Value |
| :--- | :--- |
| **Username** | `admin` |
| **Password** | `Password123!` |
| **Role** | Lead Analyst |

You can also create a new account via the **"Create Account"** tab on the sign-in page.

---

## 📁 Project Structure

```
AutoAnalyst_Pro/
├── app.py                      # Flask REST API server and routing
├── requirements.txt            # Python dependencies
├── run.bat                     # Windows 1-click launch script
├── .gitignore                  # Git ignore rules for bytecode, databases & artifacts
├── README.md                   # Repository documentation
├── data/
│   └── .gitkeep                # SQLite database runtime folder
├── engine/
│   ├── __init__.py             # Engine package initialization
│   ├── analytics.py            # Statistical profiling & correlation analysis
│   ├── auth.py                 # SQLite user persistence & password hashing
│   ├── cleaner.py              # Automated data cleaning & imputation engine
│   ├── ml_engine.py            # Clustering, anomaly detection & driver modeling
│   └── sample_datasets.py      # Real-world benchmark dataset generators
├── samples/
│   ├── ecommerce_messy.csv     # E-commerce omnichannel benchmark dataset
│   ├── healthcare_clinical_messy.csv # Healthcare patient records benchmark
│   ├── real_estate_messy.csv   # Property transactions benchmark
│   └── saas_subscriptions_messy.csv  # B2B subscription churn benchmark
├── static/
│   ├── css/
│   │   └── style.css           # Vanilla CSS design system & responsive layout
│   └── js/
│       ├── app.js              # Application logic, state & Chart.js dashboards
│       └── theme-3d.js         # 3-Mode Theme Manager & Live 3D Canvas Engine
└── templates/
    ├── index.html              # Main BI Dashboard & Analytics Studio
    └── login.html              # Authentication & User Portal
```

---

## 🧪 Automated Testing

Run the included automated test suites to verify backend endpoints, data transformations, and machine learning pipelines:

```bash
# Run server REST API tests
python test_server_api.py

# Run user authentication, session, and AI Copilot tests
python test_auth_and_features.py
```

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
