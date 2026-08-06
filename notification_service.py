import logging
import email_service
import whatsapp_service

def send(notification_payload):
    """
    Multi-channel notification dispatcher routing to Email (Brevo SMTP)
    and WhatsApp (Meta Cloud API / Twilio / CallMeBot / wa.me).
    """
    channel = str(notification_payload.get('channel', 'email')).lower()
    recipient_email = notification_payload.get('recipient_email') or 'bhosalevinayakwe@gmail.com'
    recipient_mobile = notification_payload.get('recipient_mobile') or notification_payload.get('mobile') or '8766759824'
    subject = notification_payload.get('email_subject', 'BCWA Renewal Notification')
    html_body = notification_payload.get('email_body_html', '')

    store_name = notification_payload.get('store_name', 'Medical Store')
    doc_type = notification_payload.get('document_type', 'Document')
    days_remaining = notification_payload.get('days_remaining', 0)

    email_success, email_msg = False, "Email not selected"
    wa_success, wa_msg = False, "WhatsApp not selected"

    # 1. Dispatch Email if channel is 'email' or 'both'
    if channel in ['email', 'both']:
        email_success, email_msg = email_service.send_html_email(recipient_email, subject, html_body)

    # 2. Dispatch WhatsApp if channel is 'whatsapp' or 'both'
    if channel in ['whatsapp', 'both']:
        wa_success, wa_msg = whatsapp_service.send_whatsapp_reminder(
            to_mobile=recipient_mobile,
            store_name=store_name,
            document_type=doc_type,
            days_remaining=days_remaining
        )

    if channel == 'whatsapp':
        return wa_success, wa_msg
    elif channel == 'both':
        overall_ok = email_success or wa_success
        return overall_ok, f"Email: {email_msg} | WhatsApp: {wa_msg}"
    else:
        return email_success, email_msg
