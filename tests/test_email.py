#!/usr/bin/env python
"""
Test script for email functionality.
"""
import os
from dotenv import load_dotenv
from email_utils import send_email, send_cron_job_failure_notification, send_high_failure_rate_notification

# Load environment variables from .env.dev
load_dotenv('.env.dev')

def test_simple_email():
    """Test sending a simple email"""
    subject = "Test Email from SocialScannerWeb"
    body = "This is a test email from the SocialScannerWeb application."
    recipients = os.getenv('NOTIFICATION_EMAILS', '').split(',')
    
    print(f"Sending test email to: {', '.join(recipients)}")
    result = send_email(subject, body, recipients)
    
    if result:
        print("✅ Email sent successfully!")
    else:
        print("❌ Failed to send email. Check your SMTP settings.")

def test_failure_notification():
    """Test sending a failure notification email"""
    error_message = "This is a simulated error message for testing purposes."
    
    print("Sending test failure notification email...")
    result = send_cron_job_failure_notification(error_message)
    
    if result:
        print("✅ Failure notification email sent successfully!")
    else:
        print("❌ Failed to send failure notification email.")

def test_high_failure_rate():
    """Test sending a high failure rate notification email"""
    platform = "Instagram"
    failure_rate = 75.5
    details = {
        "total": 100,
        "failed": 75,
        "succeeded": 25,
        "failures": {
            "user1": "Connection timeout",
            "user2": "Profile not found",
            "user3": "API rate limit exceeded"
        }
    }
    
    print("Sending test high failure rate notification email...")
    result = send_high_failure_rate_notification(platform, failure_rate, details)
    
    if result:
        print("✅ High failure rate notification email sent successfully!")
    else:
        print("❌ Failed to send high failure rate notification email.")

if __name__ == "__main__":
    print("Testing email functionality...")
    
    # Verify environment variables
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_username = os.getenv('SMTP_USERNAME')
    notification_emails = os.getenv('NOTIFICATION_EMAILS')
    
    if not all([smtp_server, smtp_username, notification_emails]):
        print("❌ Email configuration is incomplete. Please check your .env.dev file.")
        print(f"  SMTP_SERVER: {'✅' if smtp_server else '❌'}")
        print(f"  SMTP_USERNAME: {'✅' if smtp_username else '❌'}")
        print(f"  NOTIFICATION_EMAILS: {'✅' if notification_emails else '❌'}")
    else:
        # Run tests
        test_simple_email()
        print("\n---\n")
        test_failure_notification()
        print("\n---\n")
        test_high_failure_rate()
