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

def _execute_smtp_send(cfg, msg_obj, to_email):
    ports_to_try = [cfg['port']]
    for p in [2525, 465, 587]:
        if p not in ports_to_try:
            ports_to_try.append(p)

    last_err = None
    for port in ports_to_try:
        try:
            logging.info(f"[SMTP CONNECTING] Attempting {cfg['host']}:{port}...")
            if port == 465:
                with smtplib.SMTP_SSL(cfg['host'], port, timeout=15) as server:
                    server.login(cfg['username'], cfg['password'])
                    server.sendmail(cfg['from_email'], [to_email], msg_obj.as_string())
            else:
                with smtplib.SMTP(cfg['host'], port, timeout=15) as server:
                    server.starttls()
                    server.login(cfg['username'], cfg['password'])
                    server.sendmail(cfg['from_email'], [to_email], msg_obj.as_string())

            logging.info(f"[SMTP SUCCESS] Email delivered to {to_email} via {cfg['host']}:{port}")
            return True, f"250 OK Delivered (Port {port})"
        except Exception as e:
            last_err = str(e)
            logging.warning(f"[SMTP PORT RETRY] Port {port} failed for {cfg['host']}: {last_err}")

    logging.error(f"[SMTP FAIL] All ports failed sending to {to_email}: {last_err}")
    return False, last_err

def verify_smtp():
    """Verify SMTP configuration and test server connectivity."""
    cfg = get_smtp_config()
    if not cfg['username'] or not cfg['password']:
        return False, "Brevo / SMTP credentials (BREVO_SMTP_USERNAME/PASSWORD) not set in environment"

    ports_to_try = [cfg['port']]
    for p in [2525, 465, 587]:
        if p not in ports_to_try:
            ports_to_try.append(p)

    last_err = None
    for port in ports_to_try:
        try:
            if port == 465:
                with smtplib.SMTP_SSL(cfg['host'], port, timeout=15) as server:
                    server.login(cfg['username'], cfg['password'])
            else:
                with smtplib.SMTP(cfg['host'], port, timeout=15) as server:
                    server.starttls()
                    server.login(cfg['username'], cfg['password'])
            return True, f"Successfully authenticated with {cfg['host']}:{port}"
        except Exception as e:
            last_err = str(e)

    return False, f"SMTP Connection Error across all ports: {last_err}"

def send_email(to_email, subject, text_body):
    """Send plain text email via Brevo / SMTP."""
    cfg = get_smtp_config()
    if not cfg['username'] or not cfg['password']:
        logging.info(f"[SMTP NOTICE] Simulated text email to {to_email} (No credentials)")
        return True, "Simulated Dispatch"

    msg = MIMEText(text_body, 'plain')
    msg['Subject'] = subject
    msg['From'] = f"{cfg['from_name']} <{cfg['from_email']}>"
    msg['To'] = to_email

    return _execute_smtp_send(cfg, msg, to_email)

def send_html_email(to_email, subject, html_body):
    """Send responsive HTML email via Brevo / SMTP."""
    cfg = get_smtp_config()
    if not cfg['username'] or not cfg['password']:
        logging.info(f"[SMTP NOTICE] Simulated HTML email to {to_email} (No credentials)")
        return True, "Simulated Dispatch"

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = f"{cfg['from_name']} <{cfg['from_email']}>"
    msg['To'] = to_email

    part = MIMEText(html_body, 'html')
    msg.attach(part)

    return _execute_smtp_send(cfg, msg, to_email)

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
