import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config

logger = logging.getLogger(__name__)


def send_interview_completion_email(candidate_name, candidate_email, interview_id, score):
    if not Config.SMTP_SERVER or not Config.NOTIFICATION_EMAIL:
        logger.info("Email notifications not configured, skipping")
        return False

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Interview Completed - {candidate_name}'
        msg['From'] = Config.SMTP_USERNAME
        msg['To'] = Config.NOTIFICATION_EMAIL

        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; background: #1a1a2e; color: #e0e0e0; padding: 20px;">
            <div style="max-width: 600px; margin: 0 auto; background: #16213e; border-radius: 12px; padding: 30px;">
                <h2 style="color: #4fc3f7;">Interview Completed</h2>
                <p>A candidate has completed their interview.</p>
                <table style="width: 100%; margin: 20px 0;">
                    <tr><td style="padding: 8px; color: #9e9e9e;">Candidate:</td><td style="padding: 8px; font-weight: bold;">{candidate_name}</td></tr>
                    <tr><td style="padding: 8px; color: #9e9e9e;">Email:</td><td style="padding: 8px;">{candidate_email}</td></tr>
                    <tr><td style="padding: 8px; color: #9e9e9e;">Score:</td><td style="padding: 8px; font-weight: bold; color: {'#66bb6a' if score >= 70 else '#ffa726' if score >= 40 else '#ef5350'};">{score}/100</td></tr>
                    <tr><td style="padding: 8px; color: #9e9e9e;">Interview ID:</td><td style="padding: 8px;">#{interview_id}</td></tr>
                </table>
                <p style="color: #9e9e9e; font-size: 12px;">View full results in the admin dashboard.</p>
            </div>
        </body>
        </html>
        """

        msg.attach(MIMEText(html, 'html'))

        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Notification email sent for interview {interview_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False


def send_violation_alert(candidate_name, interview_id, violation_count):
    if not Config.SMTP_SERVER or not Config.NOTIFICATION_EMAIL:
        return False

    if violation_count < 5:
        return False

    try:
        msg = MIMEText(
            f"Alert: Candidate '{candidate_name}' (Interview #{interview_id}) "
            f"has accumulated {violation_count} proctoring violations.",
            'plain'
        )
        msg['Subject'] = f'[ALERT] High Violations - Interview #{interview_id}'
        msg['From'] = Config.SMTP_USERNAME
        msg['To'] = Config.NOTIFICATION_EMAIL

        with smtplib.SMTP(Config.SMTP_SERVER, Config.SMTP_PORT) as server:
            server.starttls()
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
            server.send_message(msg)

        return True
    except Exception as e:
        logger.error(f"Failed to send violation alert: {e}")
        return False
