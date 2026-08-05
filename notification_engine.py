import os
import uuid
import logging
import threading
import time
from datetime import datetime, timedelta
from supabase_client import db_table
import notification_service
import email_service

# -----------------------------------------------------------------------------
# REMINDER SCHEDULE STAGES (DAYS BEFORE EXPIRY)
# -----------------------------------------------------------------------------
REMINDER_STAGES = [90, 60, 30, 15, 10, 7, 3, 1, 0]

def match_reminder_stage(days_remaining):
    """Determine matching stage or expired interval (every 7 days for expired)."""
    if days_remaining in REMINDER_STAGES:
        return days_remaining
    elif days_remaining < 0 and (abs(days_remaining) % 7 == 0):
        # Every 7 days for expired documents
        return days_remaining
    return None

def generate_reminder_html_email(recipient_name, store_name, doc_name, doc_num, expiry_date_str, days_remaining, pharmacist_name=None, issue_date_str="As Per Records"):
    is_expired = days_remaining <= 0
    badge_bg = '#DC2626' if is_expired else ('#EA580C' if days_remaining <= 15 else '#2563EB')
    status_text = f"EXPIRED ({abs(days_remaining)} Days Ago)" if is_expired else (f"Expires Tomorrow" if days_remaining == 1 else f"Expires in {days_remaining} Days")

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
                    This is an official automated compliance alert regarding your document registration for <strong>{store_name}</strong>.
                </p>

                <div style="text-align: center;">
                    <span class="badge">{status_text}</span>
                </div>

                <table class="details-table">
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600; width:40%;">Medical Store:</td><td style="padding:8px 0; font-weight:700; color:#1F2937;">{store_name}</td></tr>
                    {ph_row}
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600;">Document Category:</td><td style="padding:8px 0; font-weight:700; color:#2563EB;">{doc_name}</td></tr>
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600;">License / Doc No:</td><td style="padding:8px 0; font-weight:700; color:#1F2937;">{doc_num}</td></tr>
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600;">Issue Date:</td><td style="padding:8px 0; font-weight:500; color:#4B5563;">{issue_date_str}</td></tr>
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600;">Expiry Date:</td><td style="padding:8px 0; font-weight:700; color:#DC2626;">{expiry_date_str}</td></tr>
                    <tr><td style="padding:8px 0; color:#6B7280; font-weight:600;">Remaining Days:</td><td style="padding:8px 0; font-weight:700; color:#1F2937;">{days_remaining} Days</td></tr>
                </table>

                <div class="action-box">
                    <h4 style="margin: 0 0 8px 0; color: #1E40AF;">Mandatory Action Required:</h4>
                    <p style="margin: 0; font-size: 13px; color: #1E3A8A; line-height: 1.5;">
                        Please initiate your renewal process immediately via the official regulatory portal (FDA / MSPC) and upload your renewed certificate to the BCWA Document Vault to ensure uninterrupted operations.
                    </p>
                </div>

                <p style="font-size: 13px; color: #6B7280; margin-top: 24px;">
                    Need assistance? Contact BCWA Support Desk at <a href="mailto:support@bcwaportal.in" style="color:#2563EB;">support@bcwaportal.in</a> or visit the association office in Boisar West.
                </p>
            </div>

            <div class="footer">
                <p>&copy; 2026 Boisar Welfare Chemist Association (BCWA). All Rights Reserved.</p>
                <p>This is an automated compliance notification. Please do not reply directly.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def generate_smtp_test_html_email(recipient_email, server_time, environment, supabase_status, smtp_status, render_id):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #F3F4F6; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 20px auto; background: #FFFFFF; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); }}
            .header {{ background-color: #1E3A8A; padding: 24px; text-align: center; color: #FFFFFF; }}
            .header h1 {{ margin: 0; font-size: 20px; font-weight: 700; }}
            .header p {{ margin: 4px 0 0 0; font-size: 13px; opacity: 0.9; }}
            .content {{ padding: 28px; }}
            .status-banner {{ background-color: #DEF7EC; border: 1px solid #31C48D; color: #03543F; padding: 14px; border-radius: 6px; text-align: center; font-weight: 700; font-size: 15px; margin-bottom: 20px; }}
            .info-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; }}
            .info-table td {{ padding: 10px 12px; border-bottom: 1px solid #E5E7EB; font-size: 14px; }}
            .info-label {{ color: #6B7280; font-weight: 600; width: 45%; }}
            .info-val {{ color: #1F2937; font-weight: 700; }}
            .footer {{ background-color: #F8FAFC; padding: 18px; text-align: center; font-size: 12px; color: #64748B; border-top: 1px solid #E2E8F0; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>BOISAR WELFARE CHEMIST ASSOCIATION</h1>
                <p>System Administrator SMTP Diagnostic Tool</p>
            </div>

            <div class="content">
                <div class="status-banner">
                    ✅ BCWA SMTP Test Successful
                </div>

                <p style="color: #4B5563; line-height: 1.5; font-size: 14px;">
                    This email confirms that Brevo / SMTP configuration for <strong>{recipient_email}</strong> is operational and sending emails correctly.
                </p>

                <table class="info-table">
                    <tr><td class="info-label">Server Time (UTC):</td><td class="info-val">{server_time}</td></tr>
                    <tr><td class="info-label">Environment:</td><td class="info-val">{environment}</td></tr>
                    <tr><td class="info-label">Supabase Connection:</td><td class="info-val">{supabase_status}</td></tr>
                    <tr><td class="info-label">SMTP Status:</td><td class="info-val">{smtp_status}</td></tr>
                    <tr><td class="info-label">Render Deployment ID:</td><td class="info-val">{render_id}</td></tr>
                </table>
            </div>

            <div class="footer">
                <p>&copy; 2026 Boisar Welfare Chemist Association (BCWA). System Admin Diagnostics.</p>
            </div>
        </div>
    </body>
    </html>
    """

def send_admin_test_email():
    cfg = email_service.get_smtp_config()
    to_email = cfg['from_email']
    subject = "BCWA SMTP Test Successful"

    from supabase_client import test_supabase_connection
    connected, _ = test_supabase_connection()
    supabase_status = "Connected" if connected else "Degraded"

    env_mode = os.environ.get('FLASK_ENV', 'development').capitalize()
    render_id = os.environ.get('RENDER_SERVICE_ID', 'Localhost Server')
    server_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    smtp_status = f"Connected via {cfg['host']}:{cfg['port']}"

    html = generate_smtp_test_html_email(to_email, server_time, env_mode, supabase_status, smtp_status, render_id)

    try:
        ok, msg = email_service.send_html_email(to_email, subject, html)
        if ok:
            logging.info(f"[SMTP TEST SUCCESS] Test email sent to {to_email}. Response: {msg}")
            return {'success': True, 'email': to_email, 'response': msg}
        else:
            logging.error(f"[SMTP TEST ERROR] Test email to {to_email} failed: {msg}")
            return {'success': False, 'email': to_email, 'error': msg}
    except Exception as e:
        import traceback
        err_msg = str(e)
        logging.error(f"[SMTP TEST EXCEPTION] Exception sending test email: {err_msg}\n{traceback.format_exc()}")
        return {'success': False, 'email': to_email, 'error': err_msg}

def is_duplicate_queue_item(store_id, doc_type, days_remaining):
    """Check both notification_queue and notification_logs for duplicate stage queueing."""
    try:
        q_res = db_table('notification_queue').select('*').eq('store_id', store_id).eq('document_type', doc_type).eq('days_remaining', days_remaining).execute()
        if q_res.data:
            return True

        l_res = db_table('notification_logs').select('*').eq('store_id', store_id).eq('document_type', doc_type).eq('days_remaining', days_remaining).execute()
        if l_res.data:
            return True
    except Exception:
        pass
    return False

def generate_email_subject(doc_name, days_remaining):
    if days_remaining <= 0:
        return f"BCWA Alert – {doc_name} has expired"
    elif days_remaining == 1:
        return f"BCWA Reminder – {doc_name} expires tomorrow"
    else:
        return f"BCWA Reminder – {doc_name} expires in {days_remaining} days"

def scan_and_queue_expiring_reminders():
    """
    Scan all medical stores, pharmacists, and document vault records.
    Queue matching reminders into notification_queue (NEVER send directly during scan).
    """
    today = datetime.now().date()
    queued_count = 0
    skipped_count = 0

    try:
        stores = db_table('medical_stores').select('*').execute().data or []
        pharmacists = db_table('pharmacists').select('*').execute().data or []
        documents = db_table('documents').select('*').execute().data or []
    except Exception as e:
        logging.error(f"[RENEWAL ENGINE SCAN ERROR] Failed to fetch data: {str(e)}")
        return {'queued': 0, 'skipped': 0, 'error': str(e)}

    # 1. Scan Store Documents (Drug License 20B/21B, Food License)
    for s in stores:
        store_id = s.get('id')
        store_name = s.get('store_name', 'Medical Store')
        owner_name = s.get('owner_name', 'Store Owner')
        owner_email = s.get('owner_email') or s.get('email')

        if not owner_email:
            continue

        # Drug License 20B/21B Expiry
        dl_expiry_str = s.get('dl_expiry_date')
        if dl_expiry_str:
            try:
                exp_date = datetime.strptime(dl_expiry_str, '%Y-%m-%d').date()
                days_rem = (exp_date - today).days
                stage = match_reminder_stage(days_rem)
                if stage is not None:
                    if not is_duplicate_queue_item(store_id, 'Drug License', stage):
                        doc_num = f"{s.get('dl_20b_number', '')} / {s.get('dl_21b_number', '')}"
                        subject = generate_email_subject('Drug License', stage)
                        html = generate_reminder_html_email(owner_name, store_name, 'Drug License', doc_num, dl_expiry_str, stage)
                        
                        queue_payload = {
                            'id': f"Q-DL-{uuid.uuid4().hex[:8].upper()}",
                            'store_id': store_id,
                            'recipient_name': owner_name,
                            'recipient_email': owner_email,
                            'document_type': 'Drug License',
                            'document_number': doc_num,
                            'days_remaining': stage,
                            'email_subject': subject,
                            'email_body_html': html,
                            'status': 'Pending',
                            'retry_count': 0,
                            'created_at': datetime.now().isoformat()
                        }
                        try:
                            db_table('notification_queue').insert(queue_payload).execute()
                            queued_count += 1
                        except Exception as e:
                            logging.error(f"[QUEUE INSERT ERROR] {str(e)}")
                    else:
                        skipped_count += 1
            except Exception:
                pass

        # Food License (FSSAI) Expiry
        fssai_expiry_str = s.get('fssai_expiry_date')
        if fssai_expiry_str:
            try:
                exp_date = datetime.strptime(fssai_expiry_str, '%Y-%m-%d').date()
                days_rem = (exp_date - today).days
                stage = match_reminder_stage(days_rem)
                if stage is not None:
                    if not is_duplicate_queue_item(store_id, 'Food License (FSSAI)', stage):
                        doc_num = s.get('fssai_number', 'N/A')
                        subject = generate_email_subject('Food License (FSSAI)', stage)
                        html = generate_reminder_html_email(owner_name, store_name, 'Food License (FSSAI)', doc_num, fssai_expiry_str, stage)

                        queue_payload = {
                            'id': f"Q-FS-{uuid.uuid4().hex[:8].upper()}",
                            'store_id': store_id,
                            'recipient_name': owner_name,
                            'recipient_email': owner_email,
                            'document_type': 'Food License (FSSAI)',
                            'document_number': doc_num,
                            'days_remaining': stage,
                            'email_subject': subject,
                            'email_body_html': html,
                            'status': 'Pending',
                            'retry_count': 0,
                            'created_at': datetime.now().isoformat()
                        }
                        try:
                            db_table('notification_queue').insert(queue_payload).execute()
                            queued_count += 1
                        except Exception as e:
                            logging.error(f"[QUEUE INSERT ERROR] {str(e)}")
                    else:
                        skipped_count += 1
            except Exception:
                pass

    # 2. Scan Pharmacist Documents (PPP Card, MSPC Registration)
    for p in pharmacists:
        ph_id = p.get('id')
        store_id = p.get('store_id')
        ph_name = p.get('full_name', 'Pharmacist')
        ph_email = p.get('email')

        if not ph_email:
            continue

        store = next((st for st in stores if st.get('id') == store_id), {}) if store_id else {}
        store_name = store.get('store_name', 'Associated Pharmacy')

        ppp_exp_str = p.get('ppp_expiry')
        if ppp_exp_str:
            try:
                exp_date = datetime.strptime(ppp_exp_str, '%Y-%m-%d').date()
                days_rem = (exp_date - today).days
                stage = match_reminder_stage(days_rem)
                if stage is not None:
                    if not is_duplicate_queue_item(store_id or ph_id, 'PPP Card', stage):
                        doc_num = p.get('ppp_number', 'N/A')
                        subject = generate_email_subject('PPP Card', stage)
                        html = generate_reminder_html_email(ph_name, store_name, 'PPP Card', doc_num, ppp_exp_str, stage, pharmacist_name=ph_name)

                        queue_payload = {
                            'id': f"Q-PPP-{uuid.uuid4().hex[:8].upper()}",
                            'store_id': store_id,
                            'pharmacist_id': ph_id,
                            'recipient_name': ph_name,
                            'recipient_email': ph_email,
                            'document_type': 'PPP Card',
                            'document_number': doc_num,
                            'days_remaining': stage,
                            'email_subject': subject,
                            'email_body_html': html,
                            'status': 'Pending',
                            'retry_count': 0,
                            'created_at': datetime.now().isoformat()
                        }
                        try:
                            db_table('notification_queue').insert(queue_payload).execute()
                            queued_count += 1
                        except Exception as e:
                            logging.error(f"[QUEUE INSERT ERROR] {str(e)}")
                    else:
                        skipped_count += 1
            except Exception:
                pass

    # 3. Dynamic Scan of Vault Documents (Rent Agreement, Shop Act, Inspection, Fire NOC, GST, etc.)
    for d in documents:
        d_id = d.get('id')
        store_id = d.get('store_id')
        doc_category = d.get('category', 'Vault Document')
        expiry_str = d.get('expiry_date')
        doc_num = d.get('document_number', 'N/A')

        if not expiry_str:
            continue

        store = next((st for st in stores if st.get('id') == store_id), {}) if store_id else {}
        owner_name = store.get('owner_name', 'Store Owner') if store else 'Member'
        owner_email = store.get('owner_email') or store.get('email') if store else None

        if not owner_email:
            continue

        try:
            exp_date = datetime.strptime(expiry_str, '%Y-%m-%d').date()
            days_rem = (exp_date - today).days
            stage = match_reminder_stage(days_rem)
            if stage is not None:
                if not is_duplicate_queue_item(store_id or d_id, doc_category, stage):
                    subject = generate_email_subject(doc_category, stage)
                    html = generate_reminder_html_email(owner_name, store.get('store_name', 'Medical Store'), doc_category, doc_num, expiry_str, stage)

                    queue_payload = {
                        'id': f"Q-DOC-{uuid.uuid4().hex[:8].upper()}",
                        'store_id': store_id,
                        'document_id': d_id,
                        'recipient_name': owner_name,
                        'recipient_email': owner_email,
                        'document_type': doc_category,
                        'document_number': doc_num,
                        'days_remaining': stage,
                        'email_subject': subject,
                        'email_body_html': html,
                        'status': 'Pending',
                        'retry_count': 0,
                        'created_at': datetime.now().isoformat()
                    }
                    try:
                        db_table('notification_queue').insert(queue_payload).execute()
                        queued_count += 1
                    except Exception as e:
                        logging.error(f"[QUEUE INSERT ERROR] {str(e)}")
                else:
                    skipped_count += 1
        except Exception:
            pass

    try:
        db_table('settings').upsert({'key': 'last_reminder_run', 'value': datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}).execute()
    except Exception:
        pass

    return {'queued': queued_count, 'skipped': skipped_count}

def process_notification_queue(limit=50):
    """
    Process pending & retry-eligible items in notification_queue.
    Uses exponential backoff for retries: 5 min, 30 min, 2 hours. Max retries: 3.
    """
    now = datetime.now()
    sent_count = 0
    failed_count = 0

    try:
        res = db_table('notification_queue').select('*').in_('status', ['Pending', 'Failed']).limit(limit).execute()
        items = res.data or []
    except Exception as e:
        logging.error(f"[QUEUE FETCH ERROR] {str(e)}")
        return {'sent': 0, 'failed': 0, 'error': str(e)}

    for item in items:
        item_id = item.get('id')
        retry_count = item.get('retry_count', 0)
        max_retries = item.get('max_retries', 3)
        next_retry = item.get('next_retry_at')

        if next_retry:
            try:
                retry_time = datetime.fromisoformat(next_retry.replace('Z', '+00:00'))
                if now < retry_time:
                    continue
            except Exception:
                pass

        if retry_count >= max_retries:
            # Mark permanently failed
            db_table('notification_queue').update({'status': 'FAILED', 'error_message': 'Max retries exceeded'}).eq('id', item_id).execute()
            continue

        # Update status to Sending
        db_table('notification_queue').update({'status': 'Sending'}).eq('id', item_id).execute()

        # Dispatch via multi-channel notification_service
        ok, response_msg = notification_service.send(item)
        sent_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        if ok:
            # Update queue status to Sent
            db_table('notification_queue').update({
                'status': 'Sent',
                'sent_at': sent_timestamp,
                'smtp_response': response_msg
            }).eq('id', item_id).execute()

            # Record in notification_logs history table
            log_payload = {
                'id': item_id.replace('Q-', 'N-'),
                'store_id': item.get('store_id'),
                'pharmacist_id': item.get('pharmacist_id'),
                'document_id': item.get('document_id'),
                'recipient_email': item.get('recipient_email'),
                'recipient_name': item.get('recipient_name'),
                'document_type': item.get('document_type'),
                'document_number': item.get('document_number'),
                'days_remaining': item.get('days_remaining'),
                'email_subject': item.get('email_subject'),
                'email_status': 'Sent',
                'status': 'Sent',
                'smtp_response': response_msg,
                'retry_count': retry_count,
                'sent_at': sent_timestamp,
                'delivery_status': 'Success'
            }
            try:
                db_table('notification_logs').insert(log_payload).execute()
            except Exception as e:
                logging.error(f"[LOG INSERT ERROR] {str(e)}")

            sent_count += 1
        else:
            new_retry_count = retry_count + 1
            # Exponential backoff: 5 min, 30 min, 2 hours
            backoff_minutes = 5 if new_retry_count == 1 else (30 if new_retry_count == 2 else 120)
            next_retry_at = (now + timedelta(minutes=backoff_minutes)).isoformat()

            new_status = 'FAILED' if new_retry_count >= max_retries else 'Failed'
            db_table('notification_queue').update({
                'status': new_status,
                'retry_count': new_retry_count,
                'next_retry_at': next_retry_at,
                'error_message': response_msg,
                'smtp_response': response_msg
            }).eq('id', item_id).execute()

            # Also log attempt in notification_logs
            log_payload = {
                'id': f"ERR-{item_id.replace('Q-', '')}-{new_retry_count}",
                'store_id': item.get('store_id'),
                'pharmacist_id': item.get('pharmacist_id'),
                'document_id': item.get('document_id'),
                'recipient_email': item.get('recipient_email'),
                'recipient_name': item.get('recipient_name'),
                'document_type': item.get('document_type'),
                'document_number': item.get('document_number'),
                'days_remaining': item.get('days_remaining'),
                'email_subject': item.get('email_subject'),
                'email_status': 'Failed',
                'status': 'Failed',
                'smtp_response': response_msg,
                'retry_count': new_retry_count,
                'sent_at': sent_timestamp,
                'delivery_status': 'Failed',
                'error_message': response_msg
            }
            try:
                db_table('notification_logs').insert(log_payload).execute()
            except Exception:
                pass

            failed_count += 1

    return {'sent': sent_count, 'failed': failed_count}

def run_reminder_engine():
    """Manual or scheduled execution of full scan + queue processing."""
    scan_res = scan_and_queue_expiring_reminders()
    proc_res = process_notification_queue()
    return {
        'queued': scan_res.get('queued', 0),
        'skipped': scan_res.get('skipped', 0),
        'sent': proc_res.get('sent', 0),
        'failed': proc_res.get('failed', 0)
    }

def retry_failed_queue_item(queue_id):
    """Manually retry a failed queue item."""
    try:
        res = db_table('notification_queue').select('*').eq('id', queue_id).execute()
        if not res.data:
            return False, "Queue item not found"

        item = res.data[0]
        db_table('notification_queue').update({'status': 'Pending', 'retry_count': 0, 'next_retry_at': None}).eq('id', queue_id).execute()
        proc_res = process_notification_queue()
        
        q_after = db_table('notification_queue').select('*').eq('id', queue_id).execute()
        if q_after.data and q_after.data[0].get('status') == 'Sent':
            return True, "Email resent successfully"
        else:
            err_msg = q_after.data[0].get('error_message') if q_after.data else None
            return False, err_msg or "Retry attempt failed. Check SMTP configuration."
    except Exception as e:
        return False, str(e)

def start_background_notification_scheduler():
    """Start 24-hour background scheduler thread running daily at 08:00 AM IST / periodic sweep."""
    def worker():
        while True:
            try:
                run_reminder_engine()
            except Exception as e:
                logging.error(f"[SCHEDULER ERROR] {str(e)}")
            time.sleep(3600)  # Sweep every hour

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    logging.info("[RENEWAL SCHEDULER] Automated Renewal Notification Engine daemon started.")
