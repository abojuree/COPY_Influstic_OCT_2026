#!/usr/bin/env python
"""
Email utility functions for sending notifications.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import List, Dict, Optional, Union

def send_email(subject: str, body: str, recipients: Union[str, List[str]], html: bool = False) -> bool:
    """
    Send an email using SMTP.

    Args:
        subject (str): Email subject
        body (str): Email body content
        recipients (str or list): Email recipient(s)
        html (bool): Whether the body is HTML (default: False)

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    # Get email configuration from environment variables
    smtp_server = os.getenv('SMTP_SERVER')
    smtp_port = int(os.getenv('SMTP_PORT', '587'))
    smtp_username = os.getenv('SMTP_USERNAME')
    smtp_password = os.getenv('SMTP_PASSWORD')
    sender_email = os.getenv('SENDER_EMAIL', smtp_username)

    # Check if email is configured
    if not all([smtp_server, smtp_port, smtp_username, smtp_password]):
        print(f"[{datetime.now()}] Email not configured. Set SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, and SMTP_PASSWORD environment variables.")
        return False

    # Convert single recipient to list
    if isinstance(recipients, str):
        recipients = [recipients]

    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = ', '.join(recipients)
        msg['Subject'] = subject

        # Attach body
        if html:
            msg.attach(MIMEText(body, 'html'))
        else:
            msg.attach(MIMEText(body, 'plain'))

        # Connect to SMTP server
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()  # Secure the connection
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

        print(f"[{datetime.now()}] Email sent successfully to {', '.join(recipients)}")
        return True

    except Exception as e:
        print(f"[{datetime.now()}] Failed to send email: {str(e)}")
        return False

def send_cron_job_failure_notification(error_message: str) -> bool:
    """
    Send a notification email when a cron job fails.

    Args:
        error_message (str): The error message to include in the email

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    subject = "SocialScannerWeb: Cron Job Failure Alert"

    body = f"""
    <html>
    <body>
        <h2>SocialScannerWeb Cron Job Failure</h2>
        <p>The scheduled scan job failed to complete successfully.</p>
        <h3>Error Details:</h3>
        <pre>{error_message}</pre>
        <p>Time: {datetime.now()}</p>
        <p>Please check the application logs for more details.</p>
    </body>
    </html>
    """

    # Get notification recipients from environment variable
    recipients = os.getenv('NOTIFICATION_EMAILS', '').split(',')
    if not recipients or recipients[0] == '':
        print(f"[{datetime.now()}] No notification recipients configured. Set NOTIFICATION_EMAILS environment variable.")
        return False

    return send_email(subject, body, recipients, html=True)

def send_high_failure_rate_notification(platform: str, failure_rate: float, details: Dict) -> bool:
    """
    Send a notification email when a platform's failure rate exceeds the threshold.

    Args:
        platform (str): The platform name (e.g., "Instagram", "TikTok")
        failure_rate (float): The failure rate as a percentage (0-100)
        details (dict): Additional details about the failures

    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    subject = f"SocialScannerWeb: High Failure Rate Alert for {platform}"

    # Create a table of failure details if available
    failure_details = ""
    if details.get('failures'):
        failures = details.get('failures', {})
        failure_details = "<h3>Sample Failures:</h3><ul>"
        # Get up to 5 sample failures
        sample_count = 0
        for username, error in failures.items():
            if sample_count < 5:
                failure_details += f"<li>{username}: {error}</li>"
                sample_count += 1
            else:
                break

        # Show count of additional failures
        if len(failures) > 5:
            failure_details += f"<li>... and {len(failures) - 5} more failures</li>"
        failure_details += "</ul>"

    body = f"""
    <html>
    <body>
        <h2>SocialScannerWeb High Failure Rate Alert</h2>
        <p>The failure rate for <strong>{platform}</strong> has exceeded the threshold.</p>
        <h3>Details:</h3>
        <ul>
            <li>Platform: {platform}</li>
            <li>Failure Rate: {failure_rate:.2f}%</li>
            <li>Total Accounts: {details.get('total', 0)}</li>
            <li>Failed: {details.get('failed', 0)}</li>
            <li>Succeeded: {details.get('succeeded', 0)}</li>
            <li>Time: {datetime.now()}</li>
        </ul>
        {failure_details}
        <p>Please check the application logs and scan logs for more details.</p>
    </body>
    </html>
    """

    # Get notification recipients from environment variable
    recipients = os.getenv('NOTIFICATION_EMAILS', '').split(',')
    if not recipients or recipients[0] == '':
        print(f"[{datetime.now()}] No notification recipients configured. Set NOTIFICATION_EMAILS environment variable.")
        return False

    return send_email(subject, body, recipients, html=True)
