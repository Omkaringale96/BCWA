import os
import smtplib
import logging
import random
import threading
import time
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from supabase_client import db_table

# -----------------------------------------------------------------------------
# REMINDER SCHEDULE STAGES (DAYS BEFORE EXPIRY)
# -----------------------------------------------------------------------------
REMINDER_STAGES = [90, 60, 30, 15, 10, 7, 3, 1, 0]

def get_smtp_config():
    return {
        'host': os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
        'port': int(os.environ.get('SMTP_PORT', 587)),
        'username': os.environ.get('SMTP_USERNAME', ''),
        'password': os.environ.get('SMTP_PASSWORD', ''),
        'from_email': os.environ.get('EMAIL_FROM') or os.environ.get('SMTP_USERNAME') or 'noreply@bcwaportal.in'
    }

def generate_reminder_html_email(recipient_name, store_name, doc_name, doc_num, expiry_date_str, days_remaining, pharmacist_name=None):
    is_expired = days_remaining <= 0
    badge_bg = '#DC2626' if is_expired else ('#EA580C' if days_remaining <= 15 else '#2563EB')
    status_text = "EXPIRED" if is_expired else f"Expires in {days_remaining} Days"

    ph_row = f"<tr><td style='padding:8px 0; color:#6B7280; font-weight:600;'>Assigned Pharmacist:</td><td style='padding:8px 0; font-weight:700; color:#1F2937;'>{pharmacist_name}</td></tr>" if pharmacist_name else ""

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F3F4F6; margin: 0; padding: 0; }}
            .email-container {{ max-width: 600px; margin: 20px auto; background: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
            .header {{ background-color: #1E3A8A; padding: 24px; text-align: center; color: #FFFFFF; }}
            .header h1 {{ margin: 0; font-size: 22px; font-weight: 700; letter-spacing: 0.5px; }}
            .header p {{ margin: 4px 0 0 0; font-size: 13px; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .badge {{ display: inline-block; background-color: {badge_bg}; color: #FFFFFF; padding: 6px 16px; border-radius: 50px; font-size: 14px; font-weight: 700; margin-bottom: 20px; }}
            .details-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; border-top: 1px solid #E5E7EB; border-bottom: 1px solid #E5E7EB; }}
            .action-box {{ background-color: #EFF6FF; border-left: 4px solid #2563EB; padding: 16px; border-radius: 4px; margin: 20px 0; }}
            .footer {{ background-color: #F8FAFC; padding: 20px; text-align: center; font-size: 12px; color: #64748B; border-top: 1px solid #E2E8F0; }}
        </style>
    </head>
    <body>
        <div class="email-container">
            <div class="header">
                <h1>BOISAR WELFARE CHEMIST ASSOCIATION</h1>
                <p>Official Compliance & Document Renewal Center</p>
            </div>

            <div class="content">
                <p style="font-size: 16px; color: #1F2937;">Dear <strong>{recipient_name}</strong>,</p>
                
                <p style="color: #4B5563; line-height: 1.6;">
                    This is an automated compliance notice regarding your registration document for <strong>{store_name}</strong>.
                </p>

                <div style="text-align: center;">
                    <span class="badge">{status_text}</span>
                </div>

                <table class="details-table">
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600; width:40%;">Medical Store:</td><td style="padding:8px 0; font-weight:700; color:#1F2937;">{store_name}</td></tr>
                    {ph_row}
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600;">Document Category:</td><td style="padding:8px 0; font-weight:700; color:#2563EB;">{doc_name}</td></tr>
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600;">License / Document No:</td><td style="padding:8px 0; font-weight:700; color:#1F2937;">{doc_num}</td></tr>
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600;">Expiry Date:</td><td style="padding:8px 0; font-weight:700; color:#DC2626;">{expiry_date_str}</td></tr>
                </table>

                <div class="action-box">
                    <h4 style="margin: 0 0 8px 0; color: #1E40AF;">Required Action:</h4>
                    <p style="margin: 0; font-size: 13px; color: #1E3A8A; line-height: 1.5;">
                        Please initiate your renewal process immediately via the FDA / MSPC portal and upload your renewed certificate to the BCWA Document Vault to maintain 100% compliance status.
                    </p>
                </div>

                <p style="font-size: 13px; color: #6B7280; margin-top: 24px;">
                    Need help? Contact the BCWA Support Desk at <a href="mailto:support@bcwaportal.in" style="color:#2563EB;">support@bcwaportal.in</a> or visit the association office in Boisar West.
                </p>
            </div>

            <div class="footer">
                <p>&copy; 2026 Boisar Welfare Chemist Association (BCWA). All Rights Reserved.</p>
                <p>This is an automated system email. Please do not reply directly to this message.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_smtp_email(to_email, subject, html_body):
    cfg = get_smtp_config()
    
    if not cfg['username'] or not cfg['password']:
        # If no credentials configured, record as simulated success for development
        logging.info(f"[SMTP NOTICE] Simulated email dispatch to {to_email} (SMTP credentials not configured in environment).")
        return True, "Simulated Dispatch (No SMTP credentials configured)"

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = cfg['from_email']
        msg['To'] = to_email

        part = MIMEText(html_body, 'html')
        msg.attach(part)

        if cfg['port'] == 465:
            with smtplib.SMTP_SSL(cfg['host'], cfg['port'], timeout=10) as server:
                server.login(cfg['username'], cfg['password'])
                server.sendmail(cfg['from_email'], [to_email], msg.as_string())
        else:
            with smtplib.SMTP(cfg['host'], cfg['port'], timeout=10) as server:
                server.starttls()
                server.login(cfg['username'], cfg['password'])
                server.sendmail(cfg['from_email'], [to_email], msg.as_string())

        logging.info(f"[SMTP SUCCESS] Email sent to {to_email} - Subject: {subject}")
        return True, "Delivered"
    except Exception as e:
        err_msg = str(e)
        logging.error(f"[SMTP ERROR] Failed to send email to {to_email}: {err_msg}")
        return False, err_msg

def match_reminder_stage(days):
    for stage in REMINDER_STAGES:
        if days == stage or (stage == 0 and days <= 0):
            return stage
    return None

def is_duplicate_reminder(store_id, doc_type, stage):
    try:
        res = db_table('notification_logs').select('*') \
            .eq('store_id', store_id) \
            .eq('document_type', doc_type) \
            .eq('days_remaining', stage) \
            .execute()
        return len(res.data) > 0
    except Exception:
        return False

def record_notification_log(store_id, pharmacist_id, doc_id, recipient_email, recipient_name, doc_type, days_remaining, delivery_success, error_msg=""):
    log_id = f"NLOG-{random.randint(100000, 999999)}"
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    record = {
        'id': log_id,
        'store_id': store_id,
        'pharmacist_id': pharmacist_id,
        'document_id': doc_id,
        'recipient_email': recipient_email or 'unknown@bcwaportal.in',
        'recipient_name': recipient_name or 'Store Owner',
        'document_type': doc_type,
        'days_remaining': days_remaining,
        'status': 'Sent' if delivery_success else 'Failed',
        'sent_at': now_str,
        'delivery_status': 'Success' if delivery_success else 'Failed',
        'error_message': error_msg if not delivery_success else None
    }

    try:
        db_table('notification_logs').insert(record)
    except Exception as e:
        logging.error(f"Failed to record notification log: {e}")

    return record

def scan_and_send_expiring_reminders():
    """
    Main Automated Renewal Engine scanning job.
    Scans all stores, pharmacists, and documents for matching expiry stages and dispatches emails.
    """
    logging.info("[RENEWAL ENGINE] Starting automated expiry scan...")
    today = datetime.now().date()

    try:
        stores = db_table('medical_stores').select('*').execute().data or []
        pharmacists = db_table('pharmacists').select('*').execute().data or []
        documents = db_table('documents').select('*').execute().data or []
    except Exception as e:
        logging.error(f"[RENEWAL ENGINE ERROR] Failed to fetch records from database: {e}")
        return {'processed': 0, 'sent': 0, 'failed': 0}

    sent_count = 0
    failed_count = 0
    skipped_count = 0

    # 1. SCAN MEDICAL STORES (Drug License & Food License)
    for s in stores:
        store_id = s.get('id')
        store_name = s.get('store_name', 'Medical Store')
        owner_name = s.get('owner_name', 'Owner')
        owner_email = s.get('owner_email') or s.get('contact_email') or 'owner@bcwaportal.in'

        # Drug License Expiry
        dl_expiry_str = s.get('dl_expiry_date')
        if dl_expiry_str:
            try:
                dl_exp = datetime.strptime(dl_expiry_str, '%Y-%m-%d').date()
                days = (dl_exp - today).days
                stage = match_reminder_stage(days)
                if stage is not None:
                    if not is_duplicate_reminder(store_id, 'Drug License', stage):
                        subj = f"BCWA Renewal Reminder – Drug License expires in {days} days" if days > 0 else "BCWA Urgent Notice – Drug License EXPIRED"
                        html = generate_reminder_html_email(owner_name, store_name, "Drug License (20B / 21B)", s.get('dl_20b_number', '20B-MH'), dl_expiry_str, days)
                        ok, err = send_smtp_email(owner_email, subj, html)
                        record_notification_log(store_id, None, f"DL-{store_id}", owner_email, owner_name, 'Drug License', stage, ok, err)
                        if ok: sent_count += 1
                        else: failed_count += 1
                    else:
                        skipped_count += 1
            except Exception as e:
                logging.error(f"Error processing DL for store {store_id}: {e}")

        # Food License Expiry
        fssai_expiry_str = s.get('fssai_expiry_date')
        if fssai_expiry_str:
            try:
                fssai_exp = datetime.strptime(fssai_expiry_str, '%Y-%m-%d').date()
                days = (fssai_exp - today).days
                stage = match_reminder_stage(days)
                if stage is not None:
                    if not is_duplicate_reminder(store_id, 'Food License', stage):
                        subj = f"BCWA Renewal Reminder – FSSAI License expires in {days} days" if days > 0 else "BCWA Urgent Notice – FSSAI License EXPIRED"
                        html = generate_reminder_html_email(owner_name, store_name, "FSSAI Food License", s.get('fssai_number', 'FSSAI-100'), fssai_expiry_str, days)
                        ok, err = send_smtp_email(owner_email, subj, html)
                        record_notification_log(store_id, None, f"FSSAI-{store_id}", owner_email, owner_name, 'Food License', stage, ok, err)
                        if ok: sent_count += 1
                        else: failed_count += 1
                    else:
                        skipped_count += 1
            except Exception as e:
                logging.error(f"Error processing FSSAI for store {store_id}: {e}")

    # 2. SCAN PHARMACISTS (PPP Card & MSPC Registration)
    store_map = {s['id']: s for s in stores}
    for p in pharmacists:
        ph_id = p.get('id')
        ph_name = p.get('full_name', 'Pharmacist')
        ph_email = p.get('email') or 'pharmacist@bcwaportal.in'
        store_id = p.get('store_id')
        st = store_map.get(store_id, {})
        store_name = st.get('store_name', 'Assigned Medical Store')

        # PPP Expiry
        ppp_expiry_str = p.get('ppp_expiry')
        if ppp_expiry_str:
            try:
                ppp_exp = datetime.strptime(ppp_expiry_str, '%Y-%m-%d').date()
                days = (ppp_exp - today).days
                stage = match_reminder_stage(days)
                if stage is not None:
                    if not is_duplicate_reminder(store_id or ph_id, 'PPP Card', stage):
                        subj = f"BCWA Renewal Reminder – PPP Card expires in {days} days" if days > 0 else "BCWA Urgent Notice – PPP Card EXPIRED"
                        html = generate_reminder_html_email(ph_name, store_name, "Pharmacist Professional Renewal (PPP)", p.get('ppp_number', 'PPP-100'), ppp_expiry_str, days, pharmacist_name=ph_name)
                        ok, err = send_smtp_email(ph_email, subj, html)
                        record_notification_log(store_id, ph_id, f"PPP-{ph_id}", ph_email, ph_name, 'PPP Card', stage, ok, err)
                        if ok: sent_count += 1
                        else: failed_count += 1
                    else:
                        skipped_count += 1
            except Exception as e:
                logging.error(f"Error processing PPP for pharmacist {ph_id}: {e}")

    # 3. SCAN CUSTOM DOCUMENTS
    for d in documents:
        doc_id = d.get('id')
        cat = d.get('category', 'Other Document')
        expiry_str = d.get('expiry_date')
        if expiry_str:
            try:
                exp_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
                days = (exp_date - today).days
                stage = match_reminder_stage(days)
                if stage is not None:
                    store_id = d.get('store_id')
                    st = store_map.get(store_id, {})
                    recip_name = st.get('owner_name', 'Store Owner')
                    recip_email = st.get('owner_email') or st.get('contact_email') or 'owner@bcwaportal.in'

                    if not is_duplicate_reminder(store_id or doc_id, cat, stage):
                        subj = f"BCWA Renewal Reminder – {cat} expires in {days} days" if days > 0 else f"BCWA Urgent Notice – {cat} EXPIRED"
                        html = generate_reminder_html_email(recip_name, st.get('store_name', 'Medical Store'), cat, d.get('title', doc_id), expiry_str, days)
                        ok, err = send_smtp_email(recip_email, subj, html)
                        record_notification_log(store_id, None, doc_id, recip_email, recip_name, cat, stage, ok, err)
                        if ok: sent_count += 1
                        else: failed_count += 1
                    else:
                        skipped_count += 1
            except Exception as e:
                logging.error(f"Error processing document {doc_id}: {e}")

    summary = {'sent': sent_count, 'failed': failed_count, 'skipped': skipped_count}
    logging.info(f"[RENEWAL ENGINE SCAN COMPLETE] Summary: {summary}")
    return summary

def start_background_notification_scheduler():
    """
    Launches a daemon background thread that runs scan_and_send_expiring_reminders every 24 hours.
    """
    def daemon_worker():
        while True:
            try:
                scan_and_send_expiring_reminders()
            except Exception as e:
                logging.error(f"[SCHEDULER ERROR] Background scan error: {e}")
            # Sleep 24 hours (86400 seconds)
            time.sleep(86400)

    t = threading.Thread(target=daemon_worker, daemon=True)
    t.start()
    logging.info("[RENEWAL ENGINE] Background 24-hour scheduler thread started successfully.")
