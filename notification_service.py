import logging
import email_service
# import whatsapp_service  # WHATSAPP MODULE TEMPORARILY DISABLED IN PHASE 2

def send(notification_payload):
    """
    Multi-channel notification dispatcher.
    PHASE 2 UPDATE: WhatsApp module is temporarily disabled.
    All notification dispatches route exclusively via Brevo SMTP Email engine.
    """
    channel = str(notification_payload.get('channel', 'email')).lower()
    recipient_email = notification_payload.get('recipient_email') or 'bhosalevinayakwe@gmail.com'
    recipient_mobile = notification_payload.get('recipient_mobile') or notification_payload.get('mobile') or '8766759824'
    subject = notification_payload.get('email_subject', 'BCWA Renewal Notification')
    html_body = notification_payload.get('email_body_html', '')

    store_name = notification_payload.get('store_name', 'Medical Store')
    doc_type = notification_payload.get('document_type', 'Document')
    days_remaining = notification_payload.get('days_remaining', 0)

    # 1. Dispatch Email exclusively (WhatsApp temporarily disabled in Phase 2)
    email_success, email_msg = email_service.send_html_email(recipient_email, subject, html_body)

    # =========================================================================
    # WHATSAPP ARCHITECTURE (PRESERVED - COMMENTED OUT FOR FUTURE RE-ENABLING)
    # =========================================================================
    # if channel in ['whatsapp', 'both']:
    #     wa_success, wa_msg = whatsapp_service.send_whatsapp_reminder(
    #         to_mobile=recipient_mobile,
    #         store_name=store_name,
    #         document_type=doc_type,
    #         days_remaining=days_remaining
    #     )

    logging.info(f"[NOTIFICATION SERVICE] Email dispatch to {recipient_email}: {email_msg}")
    return email_success, email_msg
