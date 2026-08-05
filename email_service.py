import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_smtp_config():
    host = os.environ.get('BREVO_SMTP_HOST') or os.environ.get('SMTP_HOST') or 'smtp-relay.brevo.com'
    port = int(os.environ.get('BREVO_SMTP_PORT') or os.environ.get('SMTP_PORT') or 587)
    username = os.environ.get('BREVO_SMTP_USERNAME') or os.environ.get('SMTP_USERNAME') or ''
    password = os.environ.get('BREVO_SMTP_PASSWORD') or os.environ.get('SMTP_PASSWORD') or ''
    from_email = os.environ.get('EMAIL_FROM') or username or 'noreply@bcwaportal.in'
    from_name = os.environ.get('EMAIL_FROM_NAME') or 'Boisar Welfare Chemist Association (BCWA)'

    return {
        'host': host,
        'port': port,
        'username': username,
        'password': password,
        'from_email': from_email,
        'from_name': from_name
    }

def verify_smtp():
    """Verify SMTP configuration and test server connectivity."""
    cfg = get_smtp_config()
    if not cfg['username'] or not cfg['password']:
        return False, "Brevo / SMTP credentials (BREVO_SMTP_USERNAME/PASSWORD) not set in environment"

    try:
        if cfg['port'] == 465:
            with smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=10) as server:
                server.login(cfg['username'], cfg['password'])
        else:
            with smtplib.SMTP(cfg['host'], cfg['port'], timeout=10) as server:
                server.starttls()
                server.login(cfg['username'], cfg['password'])
        return True, f"Successfully authenticated with {cfg['host']}:{cfg['port']}"
    except Exception as e:
        return False, f"SMTP Connection Error: {str(e)}"

def send_email(to_email, subject, text_body):
    """Send plain text email via Brevo / SMTP."""
    cfg = get_smtp_config()
    if not cfg['username'] or not cfg['password']:
        logging.info(f"[SMTP NOTICE] Simulated text email to {to_email} (No credentials)")
        return True, "Simulated Dispatch"

    try:
        msg = MIMEText(text_body, 'plain')
        msg['Subject'] = subject
        msg['From'] = f"{cfg['from_name']} <{cfg['from_email']}>"
        msg['To'] = to_email

        if cfg['port'] == 465:
            with smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=12) as server:
                server.login(cfg['username'], cfg['password'])
                server.sendmail(cfg['from_email'], [to_email], msg.as_string())
        else:
            with smtplib.SMTP(cfg['host'], cfg['port'], timeout=12) as server:
                server.starttls()
                server.login(cfg['username'], cfg['password'])
                server.sendmail(cfg['from_email'], [to_email], msg.as_string())

        logging.info(f"[SMTP SUCCESS] Text email sent to {to_email}")
        return True, "250 OK Delivered"
    except Exception as e:
        err = str(e)
        logging.error(f"[SMTP ERROR] Failed sending to {to_email}: {err}")
        return False, err

def send_html_email(to_email, subject, html_body):
    """Send responsive HTML email via Brevo / SMTP."""
    cfg = get_smtp_config()
    if not cfg['username'] or not cfg['password']:
        logging.info(f"[SMTP NOTICE] Simulated HTML email to {to_email} (No credentials)")
        return True, "Simulated Dispatch"

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = f"{cfg['from_name']} <{cfg['from_email']}>"
        msg['To'] = to_email

        part = MIMEText(html_body, 'html')
        msg.attach(part)

        if cfg['port'] == 465:
            with smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=12) as server:
                server.login(cfg['username'], cfg['password'])
                server.sendmail(cfg['from_email'], [to_email], msg.as_string())
        else:
            with smtplib.SMTP(cfg['host'], cfg['port'], timeout=12) as server:
                server.starttls()
                server.login(cfg['username'], cfg['password'])
                server.sendmail(cfg['from_email'], [to_email], msg.as_string())

        logging.info(f"[SMTP SUCCESS] HTML email sent to {to_email}")
        return True, "250 OK Delivered"
    except Exception as e:
        err = str(e)
        logging.error(f"[SMTP ERROR] Failed sending to {to_email}: {err}")
        return False, err

def send_document_expiry_email(to_email, subject, html_body):
    """Specific wrapper for document expiry notifications."""
    return send_html_email(to_email, subject, html_body)

def send_bulk_notifications(notifications_list):
    """Batch send bulk notification emails efficiently."""
    results = []
    for item in notifications_list:
        to_email = item.get('recipient_email')
        subject = item.get('email_subject')
        html_body = item.get('email_body_html')
        ok, response = send_html_email(to_email, subject, html_body)
        results.append({'id': item.get('id'), 'success': ok, 'response': response})
    return results
