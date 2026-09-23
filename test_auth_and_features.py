"""
Automated Test Suite for Authentication, Session Management, and AI Copilot Features
"""
import requests

BASE_URL = "http://127.0.0.1:5000"

def test_full_auth_and_features():
    session = requests.Session()

    print("--- 1. Testing Unauthenticated Access to / (Should Redirect to /login) ---")
    r = session.get(f"{BASE_URL}/", allow_redirects=False)
    assert r.status_code in [302, 401]
    print(f"Redirect verified. Status: {r.status_code}, Location: {r.headers.get('Location')}")

    print("\n--- 2. Testing GET /login ---")
    r = session.get(f"{BASE_URL}/login")
    assert r.status_code == 200
    assert "Sign In" in r.text
    assert "1-Click Demo" in r.text
    print("GET /login passed. Auth portal rendered.")

    print("\n--- 3. Testing POST /api/auth/login (Invalid Credentials) ---")
    r = session.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "WrongPassword"})
    assert r.status_code == 401
    print("Invalid login rejected properly (401).")

    print("\n--- 4. Testing POST /api/auth/login (Valid Demo Analyst) ---")
    r = session.post(f"{BASE_URL}/api/auth/login", json={"username": "admin", "password": "Password123!"})
    assert r.status_code == 200
    login_data = r.json()
    assert login_data["status"] == "success"
    assert login_data["user"]["username"] == "admin"
    print(f"Login passed! Welcome, {login_data['user']['full_name']} ({login_data['user']['role']})")

    print("\n--- 5. Testing GET /api/auth/me (Active Session Profile) ---")
    r = session.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200
    me = r.json()
    assert me["authenticated"] is True
    assert me["user"]["username"] == "admin"
    print("Session identity verified:", me["user"]["email"])

    print("\n--- 6. Testing GET / with Active Session ---")
    r = session.get(f"{BASE_URL}/")
    assert r.status_code == 200
    assert "AutoAnalyst" in r.text
    print("Protected dashboard accessible by authenticated session.")

    print("\n--- 7. Testing Ingestion, Clean, EDA, and ML in Session ---")
    r = session.post(f"{BASE_URL}/api/load-sample", json={"sample_id": "ecommerce"})
    assert r.status_code == 200
    print("Sample loaded into session.")

    r = session.post(f"{BASE_URL}/api/clean")
    assert r.status_code == 200
    print("Data cleaned in session.")

    r = session.post(f"{BASE_URL}/api/eda")
    assert r.status_code == 200
    print("EDA computed in session.")

    r = session.post(f"{BASE_URL}/api/ml")
    assert r.status_code == 200
    print("ML pipeline executed in session.")

    print("\n--- 8. Testing AI Data Analyst Copilot (/api/chat) ---")
    # Query 1: Drivers
    r = session.post(f"{BASE_URL}/api/chat", json={"message": "What are the primary revenue drivers?"})
    assert r.status_code == 200
    reply1 = r.json()["reply"]
    print("\n[AI Copilot - Drivers Reply]:")
    print(reply1.encode("ascii", "replace").decode("ascii"))
    assert "Driver" in reply1 or "importance" in reply1 or "leverage" in reply1 or "factor" in reply1

    # Query 2: Anomalies
    r = session.post(f"{BASE_URL}/api/chat", json={"message": "Are there any anomalies or outliers in this data?"})
    assert r.status_code == 200
    reply2 = r.json()["reply"]
    print("\n[AI Copilot - Anomalies Reply]:")
    print(reply2.encode("ascii", "replace").decode("ascii"))
    assert "Anomaly" in reply2 or "Isolation Forest" in reply2 or "outlier" in reply2

    # Query 3: Clusters
    r = session.post(f"{BASE_URL}/api/chat", json={"message": "Tell me about our entity clusters and personas"})
    assert r.status_code == 200
    reply3 = r.json()["reply"]
    print("\n[AI Copilot - Clusters Reply]:")
    print(reply3.encode("ascii", "replace").decode("ascii"))
    assert "Cluster" in reply3 or "Segmentation" in reply3 or "persona" in reply3

    print("\n--- 9. Testing Registration of a New User ---")
    import time
    ts = int(time.time())
    new_user = {
        "username": f"analyst_{ts}",
        "email": f"analyst_{ts}@company.com",
        "password": "SecurePassword99!",
        "full_name": "Sarah Connor"
    }
    r = session.post(f"{BASE_URL}/api/auth/register", json=new_user)
    assert r.status_code == 200
    reg_data = r.json()
    assert reg_data["user"]["username"] == f"analyst_{ts}"
    print(f"Registered new user successfully: {reg_data['user']['full_name']} ({reg_data['user']['username']})")

    print("\n--- 10. Testing Logout ---")
    r = session.post(f"{BASE_URL}/api/auth/logout")
    assert r.status_code == 200
    # Next call to /api/auth/me should return 401
    r = session.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 401
    print("Logout successful. Session cleared.")

    print("\n========================================================")
    print(" ALL 10 AUTHENTICATION & COPILOT TESTS PASSED (100%)!")
    print("========================================================")

if __name__ == "__main__":
    test_full_auth_and_features()
