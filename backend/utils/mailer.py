import smtplib
import os
import asyncio
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

SMTP_EMAIL = os.getenv("SMTP_EMAIL")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

def _send_email_sync(to_email: str, subject: str, html_content: str):
    """
    Synchronous function to send the email via SMTP.
    """
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        raise ValueError("SMTP_EMAIL or SMTP_PASSWORD environment variables are not set.")

    # Create the email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_EMAIL
    msg["To"] = to_email

    # Attach HTML content
    part = MIMEText(html_content, "html")
    msg.attach(part)

    # Connect to SMTP server and send
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.send_message(msg)
    except Exception as e:
        print(f"Error sending email to {to_email}: {str(e)}")
        raise e

async def send_email(to_email: str, subject: str, html_content: str):
    """
    Asynchronously sends an email without blocking the event loop.
    """
    try:
        await asyncio.to_thread(_send_email_sync, to_email, subject, html_content)
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False
