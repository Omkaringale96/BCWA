import os
import logging
import requests

def get_whatsapp_config():
    """Retrieve WhatsApp Cloud API or Twilio credentials from environment."""
    provider = os.environ.get('WHATSAPP_PROVIDER', 'meta').lower() # 'meta' or 'twilio'
    phone_id = os.environ.get('WHATSAPP_PHONE_ID') or os.environ.get('META_WHATSAPP_PHONE_ID') or ''
    access_token = os.environ.get('WHATSAPP_ACCESS_TOKEN') or os.environ.get('META_WHATSAPP_TOKEN') or ''
    business_number = os.environ.get('WHATSAPP_BUSINESS_NUMBER', '+918766759824')

    twilio_sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    twilio_token = os.environ.get('TWILIO_AUTH_TOKEN', '')
    twilio_from = os.environ.get('TWILIO_WHATSAPP_NUMBER', 'whatsapp:+14155238886')

    return {
        'provider': provider,
        'phone_id': phone_id,
        'access_token': access_token,
        'business_number': business_number,
        'twilio_sid': twilio_sid,
        'twilio_token': twilio_token,
        'twilio_from': twilio_from,
        'is_configured': bool((phone_id and access_token) or (twilio_sid and twilio_token))
    }

def verify_whatsapp_config():
    """Verify WhatsApp service credentials status."""
    cfg = get_whatsapp_config()
    if not cfg['is_configured']:
        return False, "WhatsApp API credentials (WHATSAPP_PHONE_ID / ACCESS_TOKEN or TWILIO) not set. Running in Simulated Mode."
    return True, f"WhatsApp API configured using {cfg['provider'].upper()} architecture."

def send_whatsapp_text(to_mobile, message):
    """
    Send WhatsApp text message via Meta Cloud API or Twilio.
    Falls back gracefully to Simulated Mode if credentials are absent.
    """
    cfg = get_whatsapp_config()
    target_mobile = str(to_mobile).replace(' ', '').replace('-', '')
    if not target_mobile.startswith('+'):
        if len(target_mobile) == 10:
            target_mobile = f"+91{target_mobile}"

    if not cfg['is_configured']:
        logging.info(f"[WHATSAPP NOTICE] Simulated WhatsApp text to {target_mobile}: {message[:60]}...")
        return True, f"Simulated WhatsApp Dispatch to {target_mobile}"

    try:
        if cfg['provider'] == 'meta' and cfg['phone_id'] and cfg['access_token']:
            url = f"https://graph.facebook.com/v18.0/{cfg['phone_id']}/messages"
            headers = {
                "Authorization": f"Bearer {cfg['access_token']}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "to": target_mobile.replace('+', ''),
                "type": "text",
                "text": {"body": message}
            }
            res = requests.post(url, headers=headers, json=payload, timeout=12)
            if res.status_code in [200, 201]:
                return True, "WhatsApp Message Sent via Meta Cloud API"
            else:
                return False, f"Meta API Error ({res.status_code}): {res.text}"
        
        elif cfg['twilio_sid'] and cfg['twilio_token']:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{cfg['twilio_sid']}/Messages.json"
            auth = (cfg['twilio_sid'], cfg['twilio_token'])
            data = {
                "From": cfg['twilio_from'],
                "To": f"whatsapp:{target_mobile}",
                "Body": message
            }
            res = requests.post(url, auth=auth, data=data, timeout=12)
            if res.status_code in [200, 201]:
                return True, "WhatsApp Message Sent via Twilio"
            else:
                return False, f"Twilio API Error ({res.status_code}): {res.text}"

        return True, f"Simulated WhatsApp Dispatch to {target_mobile}"
    except Exception as e:
        err = str(e)
        logging.error(f"[WHATSAPP ERROR] Failed sending to {target_mobile}: {err}")
        return False, err

def send_whatsapp_document(to_mobile, document_url, filename, caption="BCWA Portal Document Notice"):
    """Send document attachment notice via WhatsApp."""
    msg = f"📄 *BCWA Portal Document Alert*\n\n{caption}\nDocument: {filename}\nLink: {document_url}"
    return send_whatsapp_text(to_mobile, msg)

def send_whatsapp_reminder(to_mobile, store_name, document_type, days_remaining):
    """Send dynamic renewal reminder via WhatsApp."""
    if days_remaining <= 0:
        stage_str = "EXPIRED"
        emoji = "🔴"
    elif days_remaining <= 7:
        stage_str = f"URGENT ({days_remaining} Days Remaining)"
        emoji = "⚠️"
    else:
        stage_str = f"{days_remaining} Days Remaining"
        emoji = "📢"

    msg = (
        f"{emoji} *BCWA Renewal Reminder*\n\n"
        f"Dear *{store_name}*,\n\n"
        f"Your *{document_type}* renewal status is *{stage_str}*.\n"
        f"Please initiate your renewal immediately to ensure compliance.\n\n"
        f"Portal Access: https://bcwa.onrender.com\n"
        f"Boisar Welfare Chemist Association (BCWA)"
    )
    return send_whatsapp_text(to_mobile, msg)

def send_whatsapp_renewal_notice(to_mobile, store_name, document_type, expiry_date):
    """Send official renewal notice via WhatsApp."""
    msg = (
        f"📋 *BCWA Official License Expiry Notice*\n\n"
        f"Store: *{store_name}*\n"
        f"Document: *{document_type}*\n"
        f"Expiry Date: *{expiry_date}*\n\n"
        f"Log into the BCWA Store Self-Service Portal to review renewal documents.\n"
        f"https://bcwa.onrender.com"
    )
    return send_whatsapp_text(to_mobile, msg)
