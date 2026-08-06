import logging
import email_service

def send(notification_payload):
    """
    Email-Only notification dispatcher.
    All notification dispatches route exclusively via Brevo SMTP Email engine.
    """
    recipient_email = notification_payload.get('recipient_email') or 'bhosalevinayakwe@gmail.com'
    subject = notification_payload.get('email_subject', 'BCWA Renewal Notification')
    html_body = notification_payload.get('email_body_html', '')

    email_success, email_msg = email_service.send_html_email(recipient_email, subject, html_body)
    logging.info(f"[NOTIFICATION SERVICE] Email dispatch to {recipient_email}: {email_msg}")
    return email_success, email_msg
