import logging
import email_service

def send(notification_payload):
    """
    Future-ready multi-channel notification dispatcher.
    Routes to email_service currently, and can seamlessly route to 
    WhatsApp / SMS / Push notifications without modifying the reminder engine.
    """
    channel = notification_payload.get('channel', 'email')
    recipient_email = notification_payload.get('recipient_email')
    subject = notification_payload.get('email_subject', 'BCWA Notification')
    html_body = notification_payload.get('email_body_html', '')

    if channel == 'email':
        return email_service.send_html_email(recipient_email, subject, html_body)
    elif channel == 'whatsapp':
        # Placeholder for future WhatsApp API integration (e.g., Twilio/Meta Business API)
        logging.info(f"[WHATSAPP STUB] Dispatching to {recipient_email}")
        return True, "WhatsApp Queued"
    elif channel == 'sms':
        # Placeholder for future SMS API integration
        logging.info(f"[SMS STUB] Dispatching to {recipient_email}")
        return True, "SMS Queued"
    else:
        return email_service.send_html_email(recipient_email, subject, html_body)
