"""
Test suite verifying the 5 platform updates:
1. History button & backend activity logging / clearing
2. Registration email verification OTP
3. Forgot username/password recovery (sends both username & reset OTP)
4. Left sidebar UI fixes (AI Copilot badge wrap, draggable resizer, reopen on logo click)
5. Light mode dropdown text contrast rules
"""

import os
import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"

def test_all():
    session = requests.Session()

    test_id = int(time.time())
    test_email = f"alex_analyst_{test_id}@example.com"
    test_username = f"alex_user_{test_id}"
    test_password = "SecurePassword123!"
    test_fullname = "Alex Analyst"

    # Step 1: Request Registration OTP
    req_payload = {
        "username": test_username,
        "email": test_email,
        "password": test_password,
        "full_name": test_fullname
    }
    r = session.post(f"{BASE_URL}/api/auth/register-otp/request", json=req_payload)
    print("Registration OTP Request:", r.status_code, r.json())
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    resp_data = r.json()
    assert resp_data["status"] == "success"
    otp_code = resp_data.get("dev_otp")
    assert otp_code is not None, "dev_otp should be returned in simulation/dev mode"

    # Step 2: Verify Registration OTP
    v_payload = {
        "email": test_email,
        "otp_code": otp_code
    }
    r = session.post(f"{BASE_URL}/api/auth/register-otp/verify", json=v_payload)
    print("Registration OTP Verify:", r.status_code, r.json())
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    verify_resp = r.json()
    assert verify_resp["status"] == "success"
    assert verify_resp["user"]["username"] == test_username

    # Verify session is active
    r = session.get(f"{BASE_URL}/api/auth/me")
    print("Session Check /api/auth/me:", r.status_code, r.json())
    assert r.status_code == 200
    assert r.json()["authenticated"] is True

    print("\n--- 2. Testing Forgot Username / Password Recovery Flow ---")
    # Step 1: Request password recovery & username
    r = session.post(f"{BASE_URL}/api/auth/forgot-password/request", json={"email": test_email})
    print("Forgot Password Request:", r.status_code, r.json())
    assert r.status_code == 200
    forgot_data = r.json()
    assert forgot_data["status"] == "success"
    reset_otp = forgot_data.get("dev_otp")
    assert reset_otp is not None

    # Step 2: Reset password
    new_password = "BrandNewPassword2026!"
    r = session.post(f"{BASE_URL}/api/auth/forgot-password/reset", json={
        "email": test_email,
        "otp_code": reset_otp,
        "new_password": new_password
    })
    print("Password Reset:", r.status_code, r.json())
    assert r.status_code == 200
    assert r.json()["status"] == "success"

    # Step 3: Verify login works with new password
    login_session = requests.Session()
    r = login_session.post(f"{BASE_URL}/api/auth/login", json={
        "username": test_username,
        "password": new_password
    })
    print("Login with New Password:", r.status_code, r.json())
    assert r.status_code == 200
    assert r.json()["status"] == "success"

    print("\n--- 3. Testing Analysis Activity History Flow ---")
    # Load demo dataset
    r = login_session.post(f"{BASE_URL}/api/load-sample", json={"sample_id": "ecommerce"})
    assert r.status_code == 200, "Failed to load sample dataset"
    print("Sample loaded successfully.")

    # Run clean pipeline
    r = login_session.post(f"{BASE_URL}/api/clean", json={})
    assert r.status_code == 200, "Failed to clean dataset"
    print("Dataset cleaned successfully.")

    # Get User History
    r = login_session.get(f"{BASE_URL}/api/user/history")
    print("User History:", r.status_code, r.json())
    assert r.status_code == 200
    hist = r.json()["history"]
    assert len(hist) >= 2, f"Expected at least 2 history logs, got {len(hist)}"
    print(f"Recorded {len(hist)} activity items successfully.")

    # Clear History
    r = login_session.delete(f"{BASE_URL}/api/user/history")
    print("Clear History:", r.status_code, r.json())
    assert r.status_code == 200
    assert r.json()["status"] == "success"

    # Verify History is empty
    r = login_session.get(f"{BASE_URL}/api/user/history")
    assert len(r.json()["history"]) == 0
    print("History verified empty after deletion.")

    print("\n--- 4. Verifying Frontend Markup & CSS Rules ---")
    with open("templates/index.html", "r", encoding="utf-8") as f:
        index_html = f.read()
    assert "nav-history" in index_html, "History nav button missing in index.html"
    assert "history-modal" in index_html, "History modal missing in index.html"
    assert "sidebar-resizer" in index_html, "Sidebar resizer missing in index.html"
    assert "handleSidebarLogoClick" in index_html, "Logo click handler missing in index.html"
    print("templates/index.html checks passed.")

    with open("templates/login.html", "r", encoding="utf-8") as f:
        login_html = f.read()
    assert "reg-step-otp" in login_html, "Registration OTP step missing in login.html"
    assert "forgot-modal" in login_html, "Forgot password modal missing in login.html"
    assert "handleRegisterRequestOtp" in login_html, "OTP registration handler missing in login.html"
    print("templates/login.html checks passed.")

    with open("static/css/style.css", "r", encoding="utf-8") as f:
        style_css = f.read()
    assert "white-space: nowrap !important" in style_css, "nav-badge nowrap missing in style.css"
    assert ".sidebar-resizer" in style_css, "sidebar-resizer styles missing in style.css"
    assert '[data-theme="light"] select' in style_css, "Light mode select styles missing in style.css"
    assert '[data-theme="light"] option' in style_css, "Light mode option styles missing in style.css"
    assert '[data-theme="light"] .menu-item' in style_css, "Light mode dropdown item styles missing in style.css"
    print("static/css/style.css checks passed.")

    print("\n>>> ALL 5 PLATFORM UPDATES TESTED AND VERIFIED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    test_all()
