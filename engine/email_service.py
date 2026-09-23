"""
AutoAnalyst Pro - Email Notification & OTP Dispatch Service
Handles OTP delivery via standard SMTP with a clean fallback simulation for local development.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, Any


def is_smtp_configured() -> bool:
    """Checks whether SMTP environment variables are configured."""
    return bool(os.environ.get("SMTP_SERVER") and os.environ.get("SMTP_EMAIL") and os.environ.get("SMTP_PASSWORD"))


def send_verification_otp(email: str, full_name: str, otp_code: str) -> Dict[str, Any]:
    """
    Sends a 6-digit email verification OTP to new users during registration.
    """
    subject = f"AutoAnalyst Pro - Verify Your Email (Code: {otp_code})"
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 32px; border: 1px solid rgba(255,255,255,0.1); }}
        .logo {{ font-size: 22px; font-weight: 700; color: #38bdf8; margin-bottom: 24px; display: flex; align-items: center; gap: 8px; }}
        .otp-box {{ background: rgba(56, 189, 248, 0.1); border: 2px dashed #0284c7; border-radius: 12px; padding: 18px; text-align: center; font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #38bdf8; margin: 24px 0; }}
        .footer {{ font-size: 12px; color: #94a3b8; margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="logo">⚡ AutoAnalyst Pro</div>
        <h2>Welcome, {full_name}!</h2>
        <p>Thank you for joining AutoAnalyst Pro. Please use the following One-Time Password (OTP) to verify your email address and activate your account:</p>
        <div class="otp-box">{otp_code}</div>
        <p>This code will expire in <strong>10 minutes</strong>. If you did not request this account, please ignore this email.</p>
        <div class="footer">
          AutoAnalyst Pro — Autonomous Data Science & Live Dashboard Studio<br>
          Secure Analytical Environment
        </div>
      </div>
    </body>
    </html>
    """

    plain_content = f"""
    Welcome to AutoAnalyst Pro, {full_name}!
    
    Your email verification code is: {otp_code}
    This code is valid for 10 minutes.
    
    If you did not request this, please ignore this message.
    """

    return _dispatch_email(email, subject, plain_content, html_content, otp_code, "Registration Verification")


def send_recovery_email(email: str, full_name: str, username: str, otp_code: str) -> Dict[str, Any]:
    """
    Sends an account recovery email containing both the registered username and the password reset OTP.
    """
    subject = f"AutoAnalyst Pro - Account Recovery & Reset OTP (Code: {otp_code})"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f172a; color: #f8fafc; margin: 0; padding: 20px; }}
        .container {{ max-width: 520px; margin: 0 auto; background: #1e293b; border-radius: 16px; padding: 32px; border: 1px solid rgba(255,255,255,0.1); }}
        .logo {{ font-size: 22px; font-weight: 700; color: #38bdf8; margin-bottom: 24px; display: flex; align-items: center; gap: 8px; }}
        .info-card {{ background: rgba(99, 102, 241, 0.12); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 10px; padding: 14px 18px; margin: 18px 0; }}
        .otp-box {{ background: rgba(245, 158, 11, 0.1); border: 2px dashed #f59e0b; border-radius: 12px; padding: 18px; text-align: center; font-size: 32px; font-weight: 800; letter-spacing: 8px; color: #fbbf24; margin: 24px 0; }}
        .footer {{ font-size: 12px; color: #94a3b8; margin-top: 30px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 16px; }}
      </style>
    </head>
    <body>
      <div class="container">
        <div class="logo">⚡ AutoAnalyst Pro</div>
        <h2>Account Recovery Request</h2>
        <p>Hello {full_name},</p>
        <p>We received a request to recover your account credentials. Here are your account details:</p>
        
        <div class="info-card">
          <strong>👤 Registered Username:</strong> <code style="font-size: 16px; color: #818cf8;">{username}</code>
        </div>
        
        <p>To reset your password, use the One-Time Password (OTP) below:</p>
        <div class="otp-box">{otp_code}</div>
        
        <p>This code will expire in <strong>10 minutes</strong>. If you did not request this reset, your account is still secure and you can disregard this email.</p>
        <div class="footer">
          AutoAnalyst Pro — Autonomous Data Science & Live Dashboard Studio<br>
          Automated Security Dispatcher
        </div>
      </div>
    </body>
    </html>
    """

    plain_content = f"""
    AutoAnalyst Pro - Account Recovery
    
    Hello {full_name},
    
    Your registered username is: {username}
    Your password reset OTP is: {otp_code}
    
    This OTP will expire in 10 minutes.
    If you did not request this, please disregard this email.
    """

    return _dispatch_email(email, subject, plain_content, html_content, otp_code, "Password Reset & Username Recovery")


def _dispatch_email(to_email: str, subject: str, text_body: str, html_body: str, otp_code: str, purpose: str) -> Dict[str, Any]:
    """Dispatches email via SMTP if configured, or outputs simulated delivery for local dev."""
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = int(os.environ.get("SMTP_PORT", 587))
    smtp_email = os.environ.get("SMTP_EMAIL")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    smtp_use_tls = os.environ.get("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

    if is_smtp_configured():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"AutoAnalyst Pro <{smtp_email}>"
            msg["To"] = to_email

            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(smtp_server, smtp_port, timeout=10) as server:
                if smtp_use_tls:
                    server.starttls()
                server.login(smtp_email, smtp_password)
                server.sendmail(smtp_email, [to_email], msg.as_string())

            print(f"[EMAIL DISPATCHED VIA SMTP] To: {to_email} | Purpose: {purpose}")
            return {
                "success": True,
                "mode": "smtp",
                "message": f"Verification code sent to {to_email}."
            }
        except Exception as e:
            print(f"[SMTP ERROR] Failed to send email via SMTP ({e}). Falling back to local simulation.")

    # Local development / simulation mode
    print("=" * 65)
    print(f"[LOCAL DEV SIMULATED EMAIL DISPATCH]")
    print(f"   To:       {to_email}")
    print(f"   Subject:  {subject}")
    print(f"   Purpose:  {purpose}")
    print(f"   OTP Code: {otp_code}")
    print("=" * 65)

    return {
        "success": True,
        "mode": "simulation",
        "message": f"Verification code sent to {to_email}.",
        "dev_otp": otp_code  # Exposed in dev mode for testing convenience
    }
