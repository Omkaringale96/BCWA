import os
import json
import re
import random
from datetime import datetime, timedelta
from supabase_client import db_table, upload_to_supabase_storage, test_supabase_connection

def get_db_connection():
    """Compatibility wrapper returning proxy client interface"""
    return db_table

def init_db():
    """Initializes startup connection test and verifies primary admin user"""
    connected, msg = test_supabase_connection()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        res = db_table('users').select('*').eq('id', 'VIN2821').execute()
        if not res.data:
            admin_user = {
                'id': 'VIN2821',
                'name': 'Vinayak',
                'email': 'vin2821@bcwaportal.in',
                'password': '2821',
                'role': 'Administrator',
                'status': 'Active',
                'last_login': now_str,
                'created_at': now_str,
                'updated_at': now_str
            }
            db_table('users').upsert(admin_user)
    except Exception as e:
        print(f"[INIT DB WARNING] User verification deferred: {e}")

def calculate_compliance_score(store_dict, pharmacists_list, docs_count):
    """Calculates Compliance Score (0-100%) and Status"""
    score = 100
    today = datetime.now().date()

    try:
        dl_exp = datetime.strptime(store_dict.get('dl_expiry_date', '2099-12-31'), '%Y-%m-%d').date()
    except Exception:
        dl_exp = today + timedelta(days=365)

    try:
        fssai_exp = datetime.strptime(store_dict.get('fssai_expiry_date', '2099-12-31'), '%Y-%m-%d').date()
    except Exception:
        fssai_exp = today + timedelta(days=365)

    if dl_exp < today:
        score -= 40
    elif (dl_exp - today).days <= 30:
        score -= 20
    elif (dl_exp - today).days <= 90:
        score -= 10

    if fssai_exp < today:
        score -= 25
    elif (fssai_exp - today).days <= 30:
        score -= 15
    elif (fssai_exp - today).days <= 90:
        score -= 5

    if not pharmacists_list:
        score -= 25
    else:
        for p in pharmacists_list:
            try:
                ppp_exp = datetime.strptime(p.get('ppp_expiry', '2099-12-31'), '%Y-%m-%d').date()
                if ppp_exp < today:
                    score -= 15
                elif (ppp_exp - today).days <= 30:
                    score -= 10
            except Exception:
                pass

    if docs_count < 2:
        score -= 10

    score = max(0, min(100, score))

    if score >= 90:
        status_str = 'Excellent'
    elif score >= 75:
        status_str = 'Good'
    elif score >= 50:
        status_str = 'Needs Attention'
    else:
        status_str = 'Critical'

    return score, status_str

def check_duplicates(dl_20b=None, dl_21b=None, fssai=None, ppp=None, mspc=None, exclude_id=None):
    warnings = []
    
    if dl_20b:
        res = db_table('medical_stores').select('*').eq('dl_20b_number', dl_20b).execute()
        for row in res.data:
            if exclude_id and row.get('id') == exclude_id: continue
            warnings.append(f"Drug License 20B '{dl_20b}' already registered for {row.get('store_name')}.")

    if dl_21b:
        res = db_table('medical_stores').select('*').eq('dl_21b_number', dl_21b).execute()
        for row in res.data:
            if exclude_id and row.get('id') == exclude_id: continue
            warnings.append(f"Drug License 21B '{dl_21b}' already registered for {row.get('store_name')}.")

    if fssai:
        res = db_table('medical_stores').select('*').eq('fssai_number', fssai).execute()
        for row in res.data:
            if exclude_id and row.get('id') == exclude_id: continue
            warnings.append(f"Food License FSSAI '{fssai}' already registered for {row.get('store_name')}.")

    if ppp:
        res = db_table('pharmacists').select('*').eq('ppp_number', ppp).execute()
        for row in res.data:
            if exclude_id and row.get('id') == exclude_id: continue
            warnings.append(f"PPP Card Number '{ppp}' is already assigned to Pharmacist '{row.get('full_name')}'.")

    if mspc:
        res = db_table('pharmacists').select('*').eq('mspc_number', mspc).execute()
        for row in res.data:
            if exclude_id and row.get('id') == exclude_id: continue
            warnings.append(f"MSPC Registration Number '{mspc}' already exists for Pharmacist '{row.get('full_name')}'.")

    return warnings

def get_dashboard_stats():
    today = datetime.now().date()
    d90 = (today + timedelta(days=90)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    stores = db_table('medical_stores').select('*').execute().data
    pharmacists = db_table('pharmacists').select('*').execute().data
    documents = db_table('documents').select('*').execute().data
    notifications = db_table('notifications').select('*').execute().data
    activity = db_table('activity_logs').select('*').order('created_at', desc=True).limit(10).execute().data

    total_stores = len(stores)
    total_pharmacists = len(pharmacists)

    dl_expiring = sum(1 for s in stores if today_str <= str(s.get('dl_expiry_date', '')) <= d90)
    dl_expired = sum(1 for s in stores if str(s.get('dl_expiry_date', '')) < today_str)

    fssai_expiring = sum(1 for s in stores if today_str <= str(s.get('fssai_expiry_date', '')) <= d90)
    fssai_expired = sum(1 for s in stores if str(s.get('fssai_expiry_date', '')) < today_str)

    ppp_expiring = sum(1 for p in pharmacists if today_str <= str(p.get('ppp_expiry', '')) <= d90)
    ppp_expired = sum(1 for p in pharmacists if str(p.get('ppp_expiry', '')) < today_str)

    doc_expired = sum(1 for d in documents if d.get('expiry_date') and str(d.get('expiry_date')) < today_str)

    total_expired = dl_expired + fssai_expired + ppp_expired + doc_expired
    upcoming_renewals = dl_expiring + fssai_expiring + ppp_expiring

    scores = [s.get('compliance_score', 100) for s in stores] if stores else [100]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 100.0

    recent_stores = stores[:5] if len(stores) >= 5 else stores

    # Fetch notification_logs stats
    try:
        notif_logs = db_table('notification_logs').select('*').execute().data or []
        today_date_str = today.strftime('%Y-%m-%d')
        emails_sent_today = sum(1 for n in notif_logs if str(n.get('sent_at', '')).startswith(today_date_str) and n.get('delivery_status') == 'Success')
        failed_emails = sum(1 for n in notif_logs if n.get('delivery_status') == 'Failed')
    except Exception:
        emails_sent_today = 0
        failed_emails = 0

    return {
        'total_stores': total_stores,
        'total_pharmacists': total_pharmacists,
        'dl_expiring': dl_expiring,
        'fssai_expiring': fssai_expiring,
        'ppp_expiring': ppp_expiring,
        'expired_documents': total_expired,
        'upcoming_renewals': upcoming_renewals,
        'emails_sent_today': emails_sent_today,
        'failed_emails': failed_emails,
        'compliance_score': avg_score,
        'todays_notifications': len(notifications),
        'recent_activity': activity,
        'recent_stores': recent_stores
    }

def get_notification_logs(limit=100):
    try:
        return db_table('notification_logs').select('*').order('sent_at', desc=True).limit(limit).execute().data or []
    except Exception:
        return []

def get_notification_log_by_id(log_id):
    try:
        res = db_table('notification_logs').select('*').eq('id', log_id).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None

def resend_notification_log(log_id):
    log = get_notification_log_by_id(log_id)
    if not log:
        return False, "Notification log entry not found"

    from notification_engine import send_smtp_email, generate_reminder_html_email
    
    recip_email = log.get('recipient_email')
    recip_name = log.get('recipient_name', 'Valued Member')
    doc_type = log.get('document_type', 'Document')
    days_rem = log.get('days_remaining', 0)
    store_id = log.get('store_id')

    store = get_medical_store(store_id) if store_id else {}
    store_name = store.get('store_name', 'Medical Store') if store else 'Medical Store'

    subject = f"BCWA Resent Renewal Reminder – {doc_type}"
    html = generate_reminder_html_email(recip_name, store_name, doc_type, f"REF-{log_id}", "As Specified", days_rem)

    ok, err_msg = send_smtp_email(recip_email, subject, html)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    update_payload = {
        'sent_at': now_str,
        'status': 'Sent' if ok else 'Failed',
        'delivery_status': 'Success' if ok else 'Failed',
        'error_message': err_msg if not ok else None
    }
    try:
        db_table('notification_logs').update(update_payload).eq('id', log_id).execute()
    except Exception:
        pass

    return ok, err_msg

def get_medical_stores(query=None, compliance=None, status=None, limit=100, offset=0):
    stores = db_table('medical_stores').select('*').order('created_at', desc=True).limit(limit).execute().data
    pharmacists = db_table('pharmacists').select('*').execute().data

    result = []
    for s in stores:
        ph_count = sum(1 for p in pharmacists if p.get('store_id') == s.get('id'))
        s_copy = dict(s)
        s_copy['pharmacist_count'] = ph_count

        if status and s_copy.get('status') != status:
            continue
        if compliance and s_copy.get('compliance_status') != compliance:
            continue

        if query:
            q = query.strip().lower()
            match = (
                q in s_copy.get('store_name', '').lower() or
                q in s_copy.get('shop_code', '').lower() or
                q in s_copy.get('owner_name', '').lower() or
                q in s_copy.get('owner_mobile', '').lower() or
                q in s_copy.get('dl_20b_number', '').lower() or
                q in s_copy.get('dl_21b_number', '').lower() or
                q in s_copy.get('fssai_number', '').lower() or
                q in s_copy.get('area', '').lower()
            )
            if not match:
                continue

        result.append(s_copy)

    return result

def get_medical_store(store_id):
    res = db_table('medical_stores').select('*').eq('id', store_id).execute()
    if not res.data:
        return None

    store = dict(res.data[0])
    ph_res = db_table('pharmacists').select('*').eq('store_id', store_id).execute()
    doc_res = db_table('documents').select('*').eq('store_id', store_id).execute()

    store['pharmacists'] = ph_res.data
    store['documents'] = doc_res.data
    return store

def save_medical_store(data):
    store_id = data.get('id')
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    is_new = False

    if not store_id:
        is_new = True
        store_id = f"MS-{random.randint(1000, 9999)}"

    shop_code = data.get('shop_code') or f"BCWA-BSR-{random.randint(100, 999)}"

    dups = check_duplicates(
        dl_20b=data.get('dl_20b_number'),
        dl_21b=data.get('dl_21b_number'),
        fssai=data.get('fssai_number'),
        exclude_id=store_id if not is_new else None
    )

    record = {
        'id': store_id,
        'store_name': data.get('store_name'),
        'shop_code': shop_code,
        'business_type': data.get('business_type', 'Retail Pharmacy'),
        'drug_license_category': data.get('drug_license_category', '20B / 21B'),
        'owner_name': data.get('owner_name'),
        'owner_mobile': data.get('owner_mobile'),
        'owner_whatsapp': data.get('owner_whatsapp', ''),
        'owner_email': data.get('owner_email', ''),
        'owner_pan': data.get('owner_pan', ''),
        'owner_aadhaar': data.get('owner_aadhaar', ''),
        'owner_address': data.get('owner_address', ''),
        'owner_photo': data.get('owner_photo', ''),
        'store_logo': data.get('store_logo', ''),
        'store_photo': data.get('store_photo', ''),
        'contact_phone': data.get('owner_mobile', ''),
        'contact_email': data.get('owner_email', ''),
        'address_line1': data.get('address_line1', 'Boisar West'),
        'address_line2': data.get('address_line2', ''),
        'area': data.get('area', 'Boisar'),
        'city': data.get('city', 'Palghar'),
        'state': data.get('state', 'Maharashtra'),
        'pincode': data.get('pincode', '401501'),
        'google_map_url': data.get('google_map_url', ''),
        'gps_coordinates': data.get('gps_coordinates', '19.8000, 72.7500'),
        'dl_20b_number': data.get('dl_20b_number'),
        'dl_21b_number': data.get('dl_21b_number'),
        'dl_issue_date': data.get('dl_issue_date') or None,
        'dl_expiry_date': data.get('dl_expiry_date') or None,
        'dl_issuing_authority': data.get('dl_issuing_authority', 'FDA Maharashtra'),
        'dl_renewal_date': data.get('dl_renewal_date') or None,
        'fssai_number': data.get('fssai_number'),
        'fssai_issue_date': data.get('fssai_issue_date') or data.get('dl_issue_date') or None,
        'fssai_expiry_date': data.get('fssai_expiry_date') or None,
        'status': data.get('status', 'Active'),
        'updated_at': now_str
    }

    if is_new:
        record['created_at'] = now_str
        db_table('medical_stores').insert(record)
        log_activity("Office Staff", "Store Registered", f"Registered new Medical Store: {data.get('store_name')} ({shop_code})", store_id)
    else:
        db_table('medical_stores').update(record).eq('id', store_id).execute()
        log_activity("Office Staff", "Store Updated", f"Updated details for Medical Store: {data.get('store_name')}", store_id)

    # Recalculate compliance
    ph_list = db_table('pharmacists').select('*').eq('store_id', store_id).execute().data
    doc_cnt = len(db_table('documents').select('*').eq('store_id', store_id).execute().data)
    score, status_str = calculate_compliance_score(record, ph_list, doc_cnt)

    db_table('medical_stores').update({'compliance_score': score, 'compliance_status': status_str}).eq('id', store_id).execute()

    return {'id': store_id, 'shop_code': shop_code, 'warnings': dups}

def delete_medical_store(store_id):
    res = db_table('medical_stores').select('store_name').eq('id', store_id).execute()
    name = res.data[0].get('store_name') if res.data else store_id

    db_table('medical_stores').delete().eq('id', store_id).execute()
    db_table('pharmacists').update({'store_id': None}).eq('store_id', store_id).execute()
    log_activity("Administrator", "Store Deleted", f"Deleted Medical Store: {name}", store_id)
    return True

def get_pharmacists(query=None, store_id=None, limit=100):
    pharmacists = db_table('pharmacists').select('*').order('created_at', desc=True).limit(limit).execute().data
    stores = db_table('medical_stores').select('*').execute().data
    store_map = {s['id']: s for s in stores}

    result = []
    for p in pharmacists:
        if store_id and p.get('store_id') != store_id:
            continue

        p_copy = dict(p)
        st = store_map.get(p.get('store_id'))
        p_copy['store_name'] = st.get('store_name') if st else None
        p_copy['shop_code'] = st.get('shop_code') if st else None

        if query:
            q = query.strip().lower()
            match = (
                q in p_copy.get('full_name', '').lower() or
                q in p_copy.get('mspc_number', '').lower() or
                q in p_copy.get('ppp_number', '').lower() or
                q in p_copy.get('mobile', '').lower() or
                (p_copy.get('store_name') and q in p_copy.get('store_name').lower())
            )
            if not match:
                continue

        result.append(p_copy)

    return result

def save_pharmacist(data):
    ph_id = data.get('id')
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    is_new = False

    if not ph_id:
        is_new = True
        ph_id = f"PH-{random.randint(1000, 9999)}"

    dups = check_duplicates(
        ppp=data.get('ppp_number'),
        mspc=data.get('mspc_number'),
        exclude_id=ph_id if not is_new else None
    )

    record = {
        'id': ph_id,
        'store_id': data.get('store_id'),
        'full_name': data.get('full_name'),
        'photo': data.get('photo', ''),
        'mspc_number': data.get('mspc_number'),
        'ppp_number': data.get('ppp_number'),
        'ppp_expiry': data.get('ppp_expiry'),
        'reg_expiry': data.get('reg_expiry', data.get('ppp_expiry')),
        'joining_date': data.get('joining_date') or None,
        'leaving_date': data.get('leaving_date') or None,
        'mobile': data.get('mobile'),
        'email': data.get('email', ''),
        'status': data.get('status', 'Active'),
        'ppp_card_url': data.get('ppp_card_url', ''),
        'degree_cert_url': data.get('degree_cert_url', ''),
        'reg_cert_url': data.get('reg_cert_url', ''),
        'updated_at': now_str
    }

    if is_new:
        record['created_at'] = now_str
        db_table('pharmacists').insert(record)
        log_activity("Office Staff", "Pharmacist Added", f"Added Pharmacist: {data.get('full_name')} ({data.get('mspc_number')})", data.get('store_id'))
    else:
        db_table('pharmacists').update(record).eq('id', ph_id).execute()
        log_activity("Office Staff", "Pharmacist Updated", f"Updated Pharmacist: {data.get('full_name')}", data.get('store_id'))

    return {'id': ph_id, 'warnings': dups}

def transfer_pharmacist(pharmacist_id, new_store_id, joining_date=None):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today_str = datetime.now().strftime('%Y-%m-%d')

    p_res = db_table('pharmacists').select('*').eq('id', pharmacist_id).execute()
    if not p_res.data:
        return False
    p = p_res.data[0]

    s_res = db_table('medical_stores').select('store_name').eq('id', new_store_id).execute()
    new_store_name = s_res.data[0].get('store_name') if s_res.data else "New Store"

    old_s_res = db_table('medical_stores').select('store_name').eq('id', p.get('store_id', '')).execute()
    old_store_name = old_s_res.data[0].get('store_name') if old_s_res.data else "Unassigned"

    db_table('pharmacists').update({
        'store_id': new_store_id,
        'leaving_date': today_str,
        'joining_date': joining_date or today_str,
        'updated_at': now_str
    }).eq('id', pharmacist_id).execute()

    log_activity("Office Staff", "Pharmacist Transferred", f"Transferred Pharmacist {p.get('full_name')} from {old_store_name} to {new_store_name}", new_store_id)
    return True

def delete_pharmacist(pharmacist_id):
    p_res = db_table('pharmacists').select('full_name, store_id').eq('id', pharmacist_id).execute()
    name = p_res.data[0].get('full_name') if p_res.data else pharmacist_id
    store_id = p_res.data[0].get('store_id') if p_res.data else None

    db_table('pharmacists').delete().eq('id', pharmacist_id).execute()
    log_activity("Office Staff", "Pharmacist Deleted", f"Deleted Pharmacist record: {name}", store_id)
    return True

def get_documents(store_id=None, category=None):
    docs = db_table('documents').select('*').order('created_at', desc=True).execute().data
    stores = db_table('medical_stores').select('id, store_name').execute().data
    store_map = {s['id']: s['store_name'] for s in stores}

    result = []
    for d in docs:
        if store_id and d.get('store_id') != store_id:
            continue
        if category and d.get('category') != category:
            continue

        d_copy = dict(d)
        d_copy['store_name'] = store_map.get(d.get('store_id'), 'System Doc')
        result.append(d_copy)

    return result

def save_document(data):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    doc_id = data.get('id') or f"DOC-{random.randint(10000, 99999)}"
    file_name = data.get('file_name', 'document.pdf')
    size_kb = data.get('file_size_kb', 320)

    quality_status = 'Passed'
    quality_notes = 'Document resolution clear, text legible.'

    if size_kb < 30:
        quality_status = 'Warning'
        quality_notes = 'Low resolution detected. Text may be slightly blurry.'
    elif 'blur' in file_name.lower() or 'sample' in file_name.lower():
        quality_status = 'Warning'
        quality_notes = 'Blur analysis: Moderate text blur. Ensure license numbers are readable.'

    record = {
        'id': doc_id,
        'store_id': data.get('store_id'),
        'category': data.get('category', 'Drug License'),
        'title': data.get('title'),
        'file_name': file_name,
        'file_url': data.get('file_url', '/static/docs/sample.pdf'),
        'file_size_kb': size_kb,
        'version': data.get('version', 1),
        'issue_date': data.get('issue_date') or None,
        'expiry_date': data.get('expiry_date') or None,
        'quality_status': quality_status,
        'quality_notes': quality_notes,
        'uploaded_by': data.get('uploaded_by', 'Office Staff'),
        'created_at': now_str,
        'updated_at': now_str
    }

    db_table('documents').upsert(record)
    log_activity("Office Staff", "Document Uploaded", f"Uploaded {data.get('category')} for Store ID: {data.get('store_id')}", data.get('store_id'))
    return {'id': doc_id, 'quality_status': quality_status, 'quality_notes': quality_notes}

def delete_document(doc_id):
    db_table('documents').delete().eq('id', doc_id).execute()
    return True

def get_renewal_calendar_events():
    events = []
    today = datetime.now().date()

    stores = db_table('medical_stores').select('*').execute().data
    for s in stores:
        if s.get('dl_expiry_date'):
            exp = str(s['dl_expiry_date'])
            status = 'Green' if exp > (today + timedelta(days=90)).strftime('%Y-%m-%d') else ('Yellow' if exp >= today.strftime('%Y-%m-%d') else 'Red')
            events.append({
                'id': f"EV-DL-{s['id']}",
                'store_id': s['id'],
                'store_name': s['store_name'],
                'type': 'Drug License Expiry',
                'date': exp,
                'status': status
            })
        if s.get('fssai_expiry_date'):
            exp = str(s['fssai_expiry_date'])
            status = 'Green' if exp > (today + timedelta(days=90)).strftime('%Y-%m-%d') else ('Yellow' if exp >= today.strftime('%Y-%m-%d') else 'Red')
            events.append({
                'id': f"EV-FSSAI-{s['id']}",
                'store_id': s['id'],
                'store_name': s['store_name'],
                'type': 'FSSAI Expiry',
                'date': exp,
                'status': status
            })

    pharmacists = db_table('pharmacists').select('*').execute().data
    for p in pharmacists:
        if p.get('ppp_expiry'):
            exp = str(p['ppp_expiry'])
            status = 'Green' if exp > (today + timedelta(days=90)).strftime('%Y-%m-%d') else ('Yellow' if exp >= today.strftime('%Y-%m-%d') else 'Red')
            events.append({
                'id': f"EV-PPP-{p['id']}",
                'store_id': p.get('store_id'),
                'store_name': f"PPP Expiry: {p['full_name']}",
                'type': 'PPP Card Expiry',
                'date': exp,
                'status': status
            })

    return events

def get_notifications(store_id=None, is_read=None):
    res = db_table('notifications').select('*').order('created_at', desc=True).execute()
    notifs = res.data
    if store_id:
        notifs = [n for n in notifs if n.get('store_id') == store_id]
    if is_read is not None:
        notifs = [n for n in notifs if n.get('is_read') == is_read]
    return notifs

def mark_notification_read(notif_id):
    db_table('notifications').update({'is_read': True}).eq('id', notif_id).execute()
    return True

def get_activity_logs(limit=100):
    res = db_table('activity_logs').select('*').order('created_at', desc=True).limit(limit).execute()
    return res.data

def log_activity(user_name, action, details, store_id=None):
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_id = f"ACT-{random.randint(10000, 99999)}"
    db_table('activity_logs').insert({
        'id': log_id,
        'user_name': user_name,
        'action': action,
        'details': details,
        'store_id': store_id,
        'created_at': now_str
    })

def get_users():
    return db_table('users').select('*').execute().data

def save_user(data):
    user_id = data.get('id') or f"USR-{random.randint(1000, 9999)}"
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    record = {
        'id': user_id,
        'name': data.get('name'),
        'email': data.get('email'),
        'password': data.get('password', '2821'),
        'role': data.get('role', 'Office Staff'),
        'status': data.get('status', 'Active'),
        'last_login': now_str,
        'updated_at': now_str
    }
    db_table('users').upsert(record)
    return user_id
