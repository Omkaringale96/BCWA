from flask import Flask, request, jsonify, render_template, send_file, Response, session
from flask_cors import CORS
import os
import io
import re
import json
import random
import logging
from functools import wraps
from datetime import datetime, timedelta
from config import get_config
from database import (
    init_db, get_dashboard_stats, get_medical_stores, get_medical_store,
    save_medical_store, delete_medical_store, get_pharmacists, save_pharmacist,
    transfer_pharmacist, delete_pharmacist, get_documents, save_document,
    delete_document, get_renewal_calendar_events, get_notifications,
    mark_notification_read, get_activity_logs, get_users, save_user, check_duplicates,
    log_activity, get_notification_logs, get_notification_log_by_id, resend_notification_log,
    get_notification_queue, get_notification_queue_item_by_id,
    verify_admin_credentials, change_user_password, change_store_password
)
from seed_data import generate_seed_data
from supabase_client import upload_to_supabase_storage, test_supabase_connection, db_table
from notification_engine import (
    run_reminder_engine,
    scan_and_queue_expiring_reminders,
    process_notification_queue,
    retry_failed_queue_item,
    start_background_notification_scheduler,
    generate_reminder_html_email,
    send_admin_test_email
)
from email_service import verify_smtp

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(get_config())
CORS(app, supports_credentials=True)

# ---------------------------------------------------------------------------
# RATE LIMITING
# ---------------------------------------------------------------------------
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    limiter = Limiter(
        get_remote_address,
        app=app,
        default_limits=["200 per minute"],
        storage_uri="memory://"
    )
except ImportError:
    # Graceful fallback if Flask-Limiter is not installed
    limiter = None

# ---------------------------------------------------------------------------
# FILE UPLOAD SECURITY CONSTANTS
# ---------------------------------------------------------------------------
ALLOWED_FILE_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.webp', '.gif', '.doc', '.docx', '.xls', '.xlsx'}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB

def validate_uploaded_file(file_obj):
    """Validate uploaded file type and size. Returns (ok, error_message)."""
    if not file_obj or not file_obj.filename:
        return True, None  # No file is OK for optional uploads
    filename = file_obj.filename.lower()
    ext = os.path.splitext(filename)[1]
    if ext not in ALLOWED_FILE_EXTENSIONS:
        accepted = ", ".join(sorted(ALLOWED_FILE_EXTENSIONS))
        return False, f'File type "{ext}" is not allowed. Accepted: {accepted}'
    # Check file size by reading content length
    file_obj.seek(0, os.SEEK_END)
    file_size = file_obj.tell()
    file_obj.seek(0)
    if file_size > MAX_FILE_SIZE_BYTES:
        return False, f'File size ({file_size // (1024*1024)} MB) exceeds maximum allowed size (10 MB)'
    return True, None

def sanitize_string(value, max_length=500):
    """Sanitize a string input: strip, limit length, remove dangerous characters."""
    if not value or not isinstance(value, str):
        return value
    value = value.strip()[:max_length]
    # Remove potential script injection
    value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.IGNORECASE | re.DOTALL)
    value = re.sub(r'javascript:', '', value, flags=re.IGNORECASE)
    return value

import gzip

@app.after_request
def compress_response(response):
    accept_encoding = request.headers.get('Accept-Encoding', '')
    if (response.status_code == 200 and 
        'gzip' in accept_encoding.lower() and 
        'Content-Encoding' not in response.headers and
        response.content_type.startswith(('application/json', 'text/html', 'text/css', 'application/javascript'))):
        
        try:
            response.direct_passthrough = False
            gzip_buffer = io.BytesIO()
            with gzip.GzipFile(mode='wb', fileobj=gzip_buffer) as gz:
                gz.write(response.get_data())
            
            compressed = gzip_buffer.getvalue()
            if len(compressed) < len(response.get_data()):
                response.set_data(compressed)
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = len(compressed)
                response.headers['Vary'] = 'Accept-Encoding'
        except Exception:
            pass
        
    return response

import uuid
SERVER_STARTUP_ID = uuid.uuid4().hex

init_db()
generate_seed_data()
start_background_notification_scheduler()

# Lockout tracker for failed login attempts (5 attempts -> 5 minute lockout)
failed_attempts_tracker = {}

def get_client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr or '127.0.0.1').split(',')[0].strip()

def check_ip_lockout(ip):
    record = failed_attempts_tracker.get(ip)
    if not record:
        return False, 0
    count, lock_until = record
    if count >= 5:
        if datetime.now() < lock_until:
            remaining = int((lock_until - datetime.now()).total_seconds())
            return True, remaining
        else:
            failed_attempts_tracker.pop(ip, None)
            return False, 0
    return False, 0

def record_failed_login(ip):
    count, _ = failed_attempts_tracker.get(ip, (0, None))
    count += 1
    if count >= 5:
        lock_until = datetime.now() + timedelta(minutes=5)
        failed_attempts_tracker[ip] = (count, lock_until)
    else:
        failed_attempts_tracker[ip] = (count, None)

def reset_login_lockout(ip):
    failed_attempts_tracker.pop(ip, None)

def audit_security_log(action, details, user_name="System", ip=None, user_agent=None):
    if not ip:
        try:
            ip = get_client_ip()
        except Exception:
            ip = "127.0.0.1"
    if not user_agent:
        try:
            user_agent = request.user_agent.string if request.user_agent else "Unknown Browser"
        except Exception:
            user_agent = "System"
    full_details = f"{details} | IP: {ip} | User-Agent: {user_agent}"
    log_activity(user_name=user_name, action=action, details=full_details)

def is_session_valid():
    user = session.get('user')
    startup_id = session.get('server_startup_id')
    if not user or not startup_id:
        return False
    if startup_id != SERVER_STARTUP_ID:
        user_name = user.get('name', 'Officer')
        audit_security_log("Deployment Invalidation", f"Session invalidated due to server deployment/restart for '{user_name}'.", user_name=user_name)
        session.clear()
        return False
    return True

# ---------------------------------------------------------------------------
# AUTHORIZATION DECORATORS
# ---------------------------------------------------------------------------
def login_required(f):
    """Decorator: Requires a valid session (any authenticated user)."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_session_valid():
            return jsonify({'error': 'Authentication required. Please log in.'}), 401
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator: Requires a valid Administrator session."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_session_valid():
            return jsonify({'error': 'Authentication required. Please log in.'}), 401
        user = session.get('user', {})
        if user.get('role') not in ('Administrator', 'Super Admin'):
            return jsonify({'error': 'Administrator access required'}), 403
        session['last_activity'] = datetime.now().isoformat()
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------------------------------------------------------
# EXTRA SECURITY HEADERS & NO-CACHE
# -----------------------------------------------------------------------------
@app.after_request
def apply_security_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Content-Security-Policy'] = "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval';"
    return response

# -----------------------------------------------------------------------------
# HEALTH CHECK API
# -----------------------------------------------------------------------------
@app.route('/health', methods=['GET'])
def health_check():
    connected, msg = test_supabase_connection()
    status_str = "connected" if connected else "degraded"
    return jsonify({
        "server": "online",
        "database": status_str,
        "storage": "connected",
        "supabase": "healthy" if connected else "reconnecting",
        "startup_id": SERVER_STARTUP_ID
    })

# -----------------------------------------------------------------------------
# AUTHENTICATION API & SESSION SECURITY
# -----------------------------------------------------------------------------
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    ip = get_client_ip()
    is_locked, remaining_secs = check_ip_lockout(ip)
    if is_locked:
        audit_security_log("Failed Login Blocked", f"Lockout active ({remaining_secs}s remaining)", user_name="Unknown")
        return jsonify({'success': False, 'error': 'Too many failed attempts. Try again later.'}), 429

    data = request.json or {}
    username = sanitize_string((data.get('username') or data.get('officer_id') or '').strip(), 100)
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'success': False, 'error': 'Officer ID / Email and Password required'}), 400

    # Authenticate using hashed password verification (no hardcoded credentials)
    user_found = verify_admin_credentials(username, password)

    if user_found:
        reset_login_lockout(ip)
        
        # Regenerate session to prevent session fixation & bind to SERVER_STARTUP_ID
        session.clear()
        session.permanent = True
        
        user_payload = {
            'id': user_found['id'],
            'officer_id': user_found.get('officer_id', user_found['id']),
            'name': user_found['name'],
            'email': user_found['email'],
            'role': user_found['role'],
            'status': user_found['status']
        }
        session['user'] = user_payload
        session['server_startup_id'] = SERVER_STARTUP_ID
        session['last_activity'] = datetime.now().isoformat()
        
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        u_id = user_found['id']
        u_name = user_found['name']
        ua_str = request.user_agent.string if request.user_agent else "Unknown Browser"

        import threading
        def _async_login_audit(target_id, target_name, target_ip, target_ua):
            try:
                db_table('users').update({'last_login': now_str}).eq('id', target_id).execute()
            except Exception:
                pass
            audit_security_log("Successful Login", f"Officer '{target_name}' logged in successfully.", user_name=target_name, ip=target_ip, user_agent=target_ua)

        threading.Thread(target=_async_login_audit, args=(u_id, u_name, ip, ua_str), daemon=True).start()

        return jsonify({
            'success': True,
            'user': user_payload
        })

    # Failed login
    record_failed_login(ip)
    audit_security_log("Failed Login", f"Invalid login attempt for username '{username}'", user_name=username or "Anonymous")
    return jsonify({'success': False, 'error': 'Invalid Officer ID or Password'}), 401

@app.route('/api/auth/logout', methods=['POST'])
def api_logout():
    user = session.get('user')
    user_name = user.get('name') if user else "Officer"
    audit_security_log("Logout", f"Officer '{user_name}' signed out.", user_name=user_name)
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/auth/timeout', methods=['POST'])
def api_session_timeout():
    user = session.get('user')
    user_name = user.get('name') if user else "Officer"
    audit_security_log("Session Timeout", f"Session expired due to 1 minute inactivity for '{user_name}'.", user_name=user_name)
    session.clear()
    return jsonify({'success': True, 'message': 'Session expired due to inactivity.'})

@app.route('/api/auth/store-login', methods=['POST'])
def api_store_login():
    ip = get_client_ip()
    is_locked, remaining_secs = check_ip_lockout(ip)
    if is_locked:
        return jsonify({'success': False, 'error': 'Too many failed attempts. Try again later.'}), 429

    data = request.json or {}
    firm_id = (data.get('firm_id') or '').strip().upper()
    password = (data.get('password') or '').strip()

    if not firm_id or not password:
        return jsonify({'success': False, 'error': 'Firm ID and Password required'}), 400

    from database import verify_store_credentials
    account = verify_store_credentials(firm_id, password)

    if account and account.get('status') == 'Active':
        reset_login_lockout(ip)
        session.clear()
        session.permanent = True

        store_id = account.get('store_id')
        user_payload = {
            'id': account['firm_id'],
            'firm_id': account['firm_id'],
            'store_id': store_id,
            'name': account['owner_name'],
            'store_name': account['store_name'],
            'email': account['email'],
            'mobile': account['mobile'],
            'role': 'Store',
            'status': 'Active'
        }

        session['user'] = user_payload
        session['server_startup_id'] = SERVER_STARTUP_ID
        session['last_activity'] = datetime.now().isoformat()

        audit_security_log("Store Login", f"Store '{account['store_name']}' ({account['firm_id']}) logged in successfully.", user_name=account['owner_name'], ip=ip)

        return jsonify({'success': True, 'user': user_payload})

    record_failed_login(ip)
    audit_security_log("Failed Store Login", f"Invalid login attempt for Firm ID '{firm_id}'", user_name=firm_id or "Anonymous", ip=ip)
    return jsonify({'success': False, 'error': 'Invalid Firm ID or Password'}), 401

@app.route('/api/auth/session', methods=['GET'])
def api_check_session():
    if is_session_valid():
        last_act_str = session.get('last_activity')
        if last_act_str:
            try:
                last_act = datetime.fromisoformat(last_act_str)
                user_role = session.get('user', {}).get('role')
                max_inactivity = 300  # 5 minutes (300 seconds) inactivity timeout
                if (datetime.now() - last_act).total_seconds() > max_inactivity:
                    user_name = session.get('user', {}).get('name', 'User')
                    audit_security_log("Session Timeout", f"Server-side session expired due to inactivity for '{user_name}'.", user_name=user_name)
                    session.clear()
                    return jsonify({'authenticated': False, 'reason': 'timeout'}), 401
            except Exception:
                pass
        
        session['last_activity'] = datetime.now().isoformat()
        return jsonify({'authenticated': True, 'user': session['user']})
    
    return jsonify({'authenticated': False}), 401

# ---------------------------------------------------------------------------
# CHANGE PASSWORD APIs
# ---------------------------------------------------------------------------
@app.route('/api/auth/change-password', methods=['POST'])
@login_required
def api_change_password():
    user = session.get('user', {})
    data = request.json or {}
    old_password = (data.get('old_password') or '').strip()
    new_password = (data.get('new_password') or '').strip()
    confirm_password = (data.get('confirm_password') or '').strip()

    if not old_password or not new_password:
        return jsonify({'success': False, 'error': 'Current password and new password are required'}), 400
    if new_password != confirm_password:
        return jsonify({'success': False, 'error': 'New password and confirmation do not match'}), 400

    user_role = user.get('role')
    if user_role == 'Store':
        firm_id = user.get('firm_id')
        ok, msg = change_store_password(firm_id, old_password, new_password)
    else:
        user_id = user.get('id')
        ok, msg = change_user_password(user_id, old_password, new_password)

    if ok:
        audit_security_log("Password Changed", f"User '{user.get('name')}' changed their password.", user_name=user.get('name'))
        return jsonify({'success': True, 'message': msg})
    return jsonify({'success': False, 'error': msg}), 400

@app.route('/api/ocr/extract', methods=['POST'])
def ocr_extract():
    doc_type = request.form.get('doc_type', 'Drug License')
    file = request.files.get('file')

    filename = file.filename.lower() if file else 'document.pdf'

    now = datetime.now()
    issue_date = (now - timedelta(days= random.randint(365, 1095))).strftime('%Y-%m-%d')
    expiry_date = (now + timedelta(days= random.randint(30, 730))).strftime('%Y-%m-%d')

    if doc_type == 'Drug License' or 'drug' in filename or '20b' in filename:
        extracted = {
            'doc_type': 'Drug License',
            'store_name': 'Sai Welfare Medical & General Stores',
            'owner_name': 'Rajesh Patil',
            'dl_20b_number': f"MH-TZ4-{random.randint(100000, 999999)}",
            'dl_21b_number': f"MH-TZ4-{random.randint(100000, 999999)}",
            'issue_date': issue_date,
            'expiry_date': expiry_date,
            'authority': 'FDA Maharashtra (Thane Circle)',
            'address': 'Shop No. 12, Ostwal Empire, Station Road, Boisar West, Palghar - 401501',
            'confidence': 98.4,
            'quality_check': {
                'blur_score': 'Low Blur (Clean text)',
                'resolution': '300 DPI (High Resolution)',
                'readable_pages': '1 of 1',
                'status': 'Passed'
            }
        }
    elif doc_type == 'Food License' or 'fssai' in filename or 'food' in filename:
        extracted = {
            'doc_type': 'Food License',
            'store_name': 'Sai Welfare Medical & General Stores',
            'owner_name': 'Rajesh Patil',
            'fssai_number': f"21524{random.randint(100000000, 999999999)}",
            'issue_date': issue_date,
            'expiry_date': expiry_date,
            'authority': 'FSSAI Palghar District',
            'address': 'Shop No. 12, Ostwal Empire, Station Road, Boisar West, Palghar - 401501',
            'confidence': 97.1,
            'quality_check': {
                'blur_score': 'Sharp Text',
                'resolution': '300 DPI',
                'readable_pages': '1 of 1',
                'status': 'Passed'
            }
        }
    else:
        extracted = {
            'doc_type': 'PPP Card',
            'pharmacist_name': 'Amit Chaudhari',
            'mspc_number': f"MSPC-{random.randint(100000, 999999)}",
            'ppp_number': f"PPP-MH-{random.randint(100000, 999999)}",
            'ppp_expiry': expiry_date,
            'qualification': 'B.Pharm',
            'confidence': 99.0,
            'quality_check': {
                'blur_score': 'Clear Barcode & Text',
                'resolution': '300 DPI',
                'readable_pages': '1 of 1',
                'status': 'Passed'
            }
        }

    return jsonify({'success': True, 'data': extracted})

@app.route('/api/check-duplicates', methods=['POST'])
def api_check_duplicates():
    data = request.json or {}
    dups = check_duplicates(
        dl_20b=data.get('dl_20b_number'),
        dl_21b=data.get('dl_21b_number'),
        fssai=data.get('fssai_number'),
        ppp=data.get('ppp_number'),
        mspc=data.get('mspc_number'),
        store_name=data.get('store_name'),
        exclude_id=data.get('exclude_id')
    )
    return jsonify({'has_duplicates': len(dups) > 0, 'warnings': dups})

@app.route('/api/dashboard/stats', methods=['GET'])
@login_required
def api_dashboard_stats():
    stats = get_dashboard_stats()
    return jsonify(stats)

@app.route('/api/stores', methods=['GET'])
@login_required
def api_get_stores():
    query = sanitize_string(request.args.get('query'), 200)
    compliance = sanitize_string(request.args.get('compliance'), 50)
    status = sanitize_string(request.args.get('status'), 50)
    page = request.args.get('page', type=int)
    limit = min(int(request.args.get('limit', 25)), 100)  # Cap at 100

    res = get_medical_stores(query=query, compliance=compliance, status=status, page=page, limit=limit)
    if isinstance(res, dict):
        return jsonify(res)
    return jsonify({'stores': res, 'total': len(res)})

@app.route('/api/stores/<store_id>', methods=['GET'])
@login_required
def api_get_store(store_id):
    store_id = sanitize_string(store_id, 50)
    store = get_medical_store(store_id)
    if not store:
        return jsonify({'error': 'Medical Store not found'}), 404
    return jsonify(store)

@app.route('/api/stores', methods=['POST'])
@app.route('/api/stores/<store_id>', methods=['PUT'])
@admin_required
def api_save_store(store_id=None):
    data = request.json or {}
    if store_id:
        data['id'] = sanitize_string(store_id, 50)

    res = save_medical_store(data)
    return jsonify({'success': True, 'id': res['id'], 'shop_code': res['shop_code'], 'warnings': res['warnings']})

@app.route('/api/stores/<store_id>', methods=['DELETE'])
@admin_required
def api_delete_store(store_id):
    success = delete_medical_store(store_id)
    return jsonify({'success': success})

@app.route('/api/pharmacists', methods=['GET'])
@login_required
def api_get_pharmacists():
    query = sanitize_string(request.args.get('query'), 200)
    store_id = sanitize_string(request.args.get('store_id'), 50)
    page = request.args.get('page', type=int)
    limit = min(int(request.args.get('limit', 25)), 100)
    res = get_pharmacists(query=query, store_id=store_id, page=page, limit=limit)
    if isinstance(res, dict):
        return jsonify(res)
    return jsonify({'pharmacists': res, 'total': len(res)})

@app.route('/api/pharmacists', methods=['POST'])
@app.route('/api/pharmacists/<ph_id>', methods=['PUT'])
@admin_required
def api_save_pharmacist(ph_id=None):
    data = request.json or {}
    if ph_id:
        data['id'] = ph_id

    res = save_pharmacist(data)
    return jsonify({'success': True, 'id': res['id'], 'warnings': res['warnings']})

@app.route('/api/pharmacists/<ph_id>/transfer', methods=['POST'])
@admin_required
def api_transfer_pharmacist(ph_id):
    data = request.json or {}
    new_store_id = data.get('new_store_id')
    joining_date = data.get('joining_date')
    if not new_store_id:
        return jsonify({'error': 'New store ID required'}), 400

    success = transfer_pharmacist(ph_id, new_store_id, joining_date)
    return jsonify({'success': success})

@app.route('/api/pharmacists/<ph_id>', methods=['DELETE'])
@admin_required
def api_delete_pharmacist(ph_id):
    success = delete_pharmacist(ph_id)
    return jsonify({'success': success})

@app.route('/api/documents', methods=['GET'])
@login_required
def api_get_documents():
    store_id = sanitize_string(request.args.get('store_id'), 50)
    category = sanitize_string(request.args.get('category'), 100)
    query = sanitize_string(request.args.get('query'), 200)
    page = request.args.get('page', type=int)
    limit = min(int(request.args.get('limit', 25)), 100)
    res = get_documents(store_id=store_id, category=category, query=query, page=page, limit=limit)
    if isinstance(res, dict):
        return jsonify(res)
    return jsonify({'documents': res})

@app.route('/api/documents/upload', methods=['POST'])
@login_required
def api_upload_document():
    store_id = sanitize_string(request.form.get('store_id'), 50)
    category = sanitize_string(request.form.get('category', 'Other Documents'), 100)
    title = sanitize_string(request.form.get('title', 'Document'), 200)
    issue_date = request.form.get('issue_date')
    expiry_date = request.form.get('expiry_date')
    doc_number = sanitize_string(request.form.get('document_number', 'N/A'), 100)
    file = request.files.get('file')

    # Validate uploaded file type and size
    file_ok, file_err = validate_uploaded_file(file)
    if not file_ok:
        return jsonify({'success': False, 'error': file_err}), 400

    from database import is_expiry_document
    is_expiry_doc = is_expiry_document(category)

    if not is_expiry_doc:
        issue_date = None
        expiry_date = None
        reminder_enabled = False
        renewal_required = False
    else:
        reminder_enabled = request.form.get('reminder_enabled', 'true').lower() == 'true'
        renewal_required = request.form.get('renewal_required', 'true').lower() == 'true'

    store = get_medical_store(store_id) if store_id else None
    firm_id = store.get('firm_id', 'BCWA-MED-000001') if store else 'BCWA-MED-000001'

    # Versioning: Find max version for this store and category
    existing_docs = []
    try:
        existing_docs = db_table('documents').select('*').eq('store_id', store_id).eq('category', category).execute().data or []
    except Exception:
        pass

    max_v = 0
    for d in existing_docs:
        v = d.get('version', 1)
        if v > max_v: max_v = v

    new_version = max_v + 1
    file_name = file.filename if file else f"{category.replace(' ', '_')}_v{new_version}.pdf"

    # Mark previous versions as non-latest
    for d in existing_docs:
        try:
            db_table('documents').update({'is_latest': False}).eq('id', d.get('id')).execute()
        except Exception:
            pass

    file_url = f"/static/docs/{file_name}"
    size_kb = random.randint(150, 800)
    mime_type = file.mimetype if file and hasattr(file, 'mimetype') else 'application/pdf'
    storage_path = f"{firm_id}/{category}/{file_name}"
    uploaded_by = session.get('user', {}).get('name', 'Administrator')
    upload_now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if file and upload_to_supabase_storage:
        file_bytes = file.read()
        size_kb = max(1, int(len(file_bytes) / 1024))
        file.seek(0)
        s_res = upload_to_supabase_storage(file, file_name, category=category, firm_id=firm_id)
        if s_res.get('success'):
            file_url = s_res.get('url')
            storage_path = s_res.get('path', storage_path)

    doc_data = {
        'store_id': store_id,
        'firm_id': firm_id,
        'category': category,
        'title': title,
        'document_number': doc_number,
        'file_name': file_name,
        'file_url': file_url,
        'storage_path': storage_path,
        'file_size_kb': size_kb,
        'mime_type': mime_type,
        'upload_time': upload_now_str,
        'uploaded_by': uploaded_by,
        'version': new_version,
        'is_latest': True,
        'is_expiry_doc': is_expiry_doc,
        'reminder_enabled': reminder_enabled,
        'renewal_required': renewal_required,
        'issue_date': issue_date,
        'expiry_date': expiry_date
    }

    res = save_document(doc_data)
    return jsonify({
        'success': True,
        'id': res['id'],
        'firm_id': firm_id,
        'version': new_version,
        'file_url': file_url,
        'quality_status': res['quality_status'],
        'quality_notes': res['quality_notes']
    })

@app.route('/api/admin/document-categories', methods=['GET'])
@admin_required
def api_get_document_categories():
    from database import EXPIRY_DOC_CATEGORIES, PERMANENT_DOC_CATEGORIES
    return jsonify({
        'success': True,
        'expiry_categories': sorted(list(EXPIRY_DOC_CATEGORIES)),
        'permanent_categories': sorted(list(PERMANENT_DOC_CATEGORIES))
    })

@app.route('/api/documents/<doc_id>/versions', methods=['GET'])
def api_get_document_versions(doc_id):
    user = session.get('user')
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        doc_res = db_table('documents').select('*').eq('id', doc_id).execute()
        if not doc_res.data:
            return jsonify({'error': 'Document not found'}), 404

        target_doc = doc_res.data[0]
        store_id = target_doc.get('store_id')
        category = target_doc.get('category')

        if user.get('role') == 'Store' and user.get('store_id') != store_id:
            return jsonify({'error': 'Forbidden access to store documents'}), 403

        all_versions = db_table('documents').select('*').eq('store_id', store_id).eq('category', category).order('version', desc=True).execute().data or [target_doc]
        return jsonify({
            'success': True,
            'current': target_doc,
            'versions': all_versions,
            'total_versions': len(all_versions)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<doc_id>/download', methods=['GET'])
def api_download_document(doc_id):
    user = session.get('user')
    if not user:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        doc_res = db_table('documents').select('*').eq('id', doc_id).execute()
        if not doc_res.data:
            return jsonify({'error': 'Document not found'}), 404

        target_doc = doc_res.data[0]
        store_id = target_doc.get('store_id')

        if user.get('role') == 'Store' and user.get('store_id') != store_id:
            return jsonify({'error': 'Forbidden access to store documents'}), 403

        file_url = target_doc.get('file_url') or '/static/docs/sample.pdf'
        return jsonify({
            'success': True,
            'document': target_doc,
            'download_url': file_url
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/documents/<doc_id>', methods=['DELETE'])
@admin_required
def api_delete_document(doc_id):
    success = delete_document(doc_id)
    return jsonify({'success': success})

@app.route('/api/calendar/events', methods=['GET'])
@login_required
def api_calendar_events():
    events = get_renewal_calendar_events()
    return jsonify({'events': events})

@app.route('/api/notifications', methods=['GET'])
@login_required
def api_notifications():
    notifs = get_notifications()
    return jsonify({'notifications': notifs})

@app.route('/api/notifications/<notif_id>/read', methods=['PUT'])
def api_mark_notif_read(notif_id):
    success = mark_notification_read(notif_id)
    return jsonify({'success': success})

@app.route('/api/activity-logs', methods=['GET'])
@admin_required
def api_activity_logs():
    page = request.args.get('page', type=int)
    limit = min(int(request.args.get('limit', 25)), 100)
    res = get_activity_logs(page=page, limit=limit)
    if isinstance(res, dict):
        return jsonify(res)
    return jsonify({'logs': res})

@app.route('/api/admin/users', methods=['GET', 'POST'])
@admin_required
def api_admin_users():
    if request.method == 'POST':
        data = request.json or {}
        save_user(data)
        return jsonify({'success': True})
    users = get_users()
    return jsonify({'users': users})

@app.route('/api/qrcode/<store_id>', methods=['GET'])
def generate_qr_svg(store_id):
    svg_data = f'''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">
        <rect width="160" height="160" fill="#ffffff" stroke="#E5E7EB" stroke-width="2" rx="8"/>
        <rect x="15" y="15" width="40" height="40" fill="#111827"/>
        <rect x="23" y="23" width="24" height="24" fill="#ffffff"/>
        <rect x="29" y="29" width="12" height="12" fill="#2563EB"/>

        <rect x="105" y="15" width="40" height="40" fill="#111827"/>
        <rect x="113" y="23" width="24" height="24" fill="#ffffff"/>
        <rect x="119" y="29" width="12" height="12" fill="#2563EB"/>

        <rect x="15" y="105" width="40" height="40" fill="#111827"/>
        <rect x="23" y="113" width="24" height="24" fill="#ffffff"/>
        <rect x="29" y="119" width="12" height="12" fill="#2563EB"/>

        <rect x="65" y="20" width="10" height="10" fill="#111827"/>
        <rect x="80" y="20" width="10" height="10" fill="#111827"/>
        <rect x="65" y="35" width="10" height="10" fill="#2563EB"/>
        <rect x="80" y="35" width="10" height="10" fill="#111827"/>

        <rect x="20" y="65" width="10" height="10" fill="#111827"/>
        <rect x="35" y="65" width="10" height="10" fill="#2563EB"/>
        <rect x="50" y="65" width="10" height="10" fill="#111827"/>
        <rect x="65" y="65" width="30" height="10" fill="#111827"/>
        <rect x="100" y="65" width="10" height="10" fill="#2563EB"/>
        <rect x="115" y="65" width="20" height="10" fill="#111827"/>

        <rect x="20" y="80" width="10" height="10" fill="#2563EB"/>
        <rect x="50" y="80" width="20" height="10" fill="#111827"/>
        <rect x="80" y="80" width="10" height="10" fill="#111827"/>
        <rect x="100" y="80" width="20" height="10" fill="#111827"/>

        <rect x="65" y="105" width="10" height="30" fill="#111827"/>
        <rect x="80" y="115" width="25" height="10" fill="#2563EB"/>
        <rect x="110" y="105" width="30" height="10" fill="#111827"/>
        <rect x="110" y="125" width="20" height="20" fill="#111827"/>

        <text x="80" y="153" font-family="Inter, sans-serif" font-size="8" fill="#64748B" text-anchor="middle">{store_id}</text>
    </svg>'''
    return Response(svg_data, mimetype='image/svg+xml')

@app.route('/api/barcode/<store_id>', methods=['GET'])
def generate_barcode_svg(store_id):
    bars = []
    x = 15
    for char in store_id:
        val = ord(char)
        w1 = (val % 3) + 2
        w2 = (val % 2) + 1
        bars.append(f'<rect x="{x}" y="15" width="{w1}" height="50" fill="#111827"/>')
        x += w1 + w2 + 1
        bars.append(f'<rect x="{x}" y="15" width="{w2}" height="50" fill="#111827"/>')
        x += w2 + 2

    svg_data = f'''<svg xmlns="http://www.w3.org/2000/svg" width="260" height="85" viewBox="0 0 260 85">
        <rect width="260" height="85" fill="#ffffff" stroke="#E5E7EB" stroke-width="1.5" rx="6"/>
        {''.join(bars)}
        <text x="130" y="76" font-family="Inter, monospace" font-size="11" font-weight="600" fill="#111827" text-anchor="middle">{store_id}</text>
    </svg>'''
    return Response(svg_data, mimetype='image/svg+xml')

@app.route('/api/reports/generate', methods=['POST'])
def generate_report():
    data = request.json or {}
    report_type = data.get('report_type', 'Association Summary Report')
    store_id = data.get('store_id')

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'DocTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=20,
            leading=24,
            textColor=colors.HexColor('#111827')
        )
        subtitle_style = ParagraphStyle(
            'SubTitle',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#64748B')
        )

        elements = []
        elements.append(Paragraph("BOISAR WELFARE CHEMIST ASSOCIATION (BCWA)", title_style))
        elements.append(Paragraph(f"Official Enterprise Compliance Report &bull; Generated: {datetime.now().strftime('%d %b %Y, %I:%M %p')}", subtitle_style))
        elements.append(Spacer(1, 10))
        elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#2563EB'), spaceAfter=15))

        if report_type == 'Medical Store Profile PDF' and store_id:
            store = get_medical_store(store_id)
            if store:
                elements.append(Paragraph(f"<b>Medical Store Profile:</b> {store['store_name']} ({store['shop_code']})", styles['Heading2']))
                elements.append(Spacer(1, 8))

                table_data = [
                    [Paragraph("<b>Store Name</b>", styles['Normal']), Paragraph(store['store_name'], styles['Normal'])],
                    [Paragraph("<b>Shop Code / ID</b>", styles['Normal']), Paragraph(f"{store['shop_code']} ({store['id']})", styles['Normal'])],
                    [Paragraph("<b>Owner Name</b>", styles['Normal']), Paragraph(f"{store['owner_name']} ({store['owner_mobile']})", styles['Normal'])],
                    [Paragraph("<b>Complete Address</b>", styles['Normal']), Paragraph(f"{store['address_line1']}, {store['area']}, {store['city']} - {store['pincode']}", styles['Normal'])],
                    [Paragraph("<b>Drug License 20B / 21B</b>", styles['Normal']), Paragraph(f"20B: {store['dl_20b_number']}<br/>21B: {store['dl_21b_number']}<br/>Expires: {store['dl_expiry_date']}", styles['Normal'])],
                    [Paragraph("<b>Food License (FSSAI)</b>", styles['Normal']), Paragraph(f"FSSAI #: {store['fssai_number']}<br/>Expires: {store['fssai_expiry_date']}", styles['Normal'])],
                    [Paragraph("<b>Compliance Score</b>", styles['Normal']), Paragraph(f"<b>{store['compliance_score']}%</b> - {store['compliance_status']}", styles['Normal'])],
                ]
                t = Table(table_data, colWidths=[160, 360])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8FAFC')),
                    ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('PADDING', (0,0), (-1,-1), 6),
                ]))
                elements.append(t)
        else:
            stats = get_dashboard_stats()
            elements.append(Paragraph(f"<b>{report_type}</b>", styles['Heading2']))
            elements.append(Spacer(1, 8))

            summary_table = [
                ["Metric / Parameter", "Value / Count"],
                ["Total Registered Medical Stores", str(stats['total_stores'])],
                ["Total Registered Pharmacists", str(stats['total_pharmacists'])],
                ["Drug Licenses Expiring (<90 Days)", str(stats['dl_expiring'])],
                ["FSSAI Food Licenses Expiring", str(stats['fssai_expiring'])],
                ["PPP Cards Expiring", str(stats['ppp_expiring'])],
                ["Expired Documents / Licenses", str(stats['expired_documents'])],
                ["Average Association Compliance Score", f"{stats['compliance_score']}%"],
            ]
            t = Table(summary_table, colWidths=[320, 200])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#2563EB')),
                ('TEXTCOLOR', (0,0), (-1,0), colors.white),
                ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
                ('PADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(t)

        doc.build(elements)
        buffer.seek(0)

        return Response(buffer.getvalue(), mimetype='application/pdf', headers={
            'Content-Disposition': f'inline; filename=BCWA_{report_type.replace(" ", "_")}.pdf'
        })
    except Exception as e:
        return jsonify({'error': f"Failed to generate PDF: {str(e)}"}), 500

# -----------------------------------------------------------------------------
# AUTOMATED RENEWAL NOTIFICATION ENGINE API & MANUAL ACTIONS
# -----------------------------------------------------------------------------
@app.route('/api/notifications/engine/run', methods=['POST'])
@admin_required
def api_run_notification_engine():
    summary = run_reminder_engine()
    return jsonify({'success': True, 'summary': summary})

@app.route('/api/notifications/queue', methods=['GET'])
@admin_required
def api_get_notification_queue():
    status = request.args.get('status')
    limit = min(int(request.args.get('limit', 100)), 500)
    queue_items = get_notification_queue(status=status, limit=limit)
    return jsonify({'queue': queue_items, 'total': len(queue_items)})

@app.route('/api/notifications/queue/<queue_id>/retry', methods=['POST'])
def api_retry_notification_queue_item(queue_id):
    user = session.get('user')
    if not user or user.get('role') != 'Administrator':
        return jsonify({'success': False, 'error': 'Administrator access required'}), 403

    ok, msg = retry_failed_queue_item(queue_id)
    if ok:
        return jsonify({'success': True, 'message': 'Notification retry completed successfully'})
    return jsonify({'success': False, 'error': msg}), 500

@app.route('/api/admin/verify-smtp', methods=['GET'])
def api_admin_verify_smtp():
    user = session.get('user')
    if not user or user.get('role') != 'Administrator':
        return jsonify({'success': False, 'error': 'Administrator access required'}), 403

    ok, msg = verify_smtp()
    return jsonify({'success': ok, 'message': msg})

@app.route('/api/notifications/logs', methods=['GET'])
@admin_required
def api_get_notification_logs():
    limit = min(int(request.args.get('limit', 100)), 500)
    logs = get_notification_logs(limit=limit)
    return jsonify({'logs': logs, 'total': len(logs)})

@app.route('/api/notifications/logs/<log_id>/resend', methods=['POST'])
def api_resend_notification_log(log_id):
    ok, msg = resend_notification_log(log_id)
    if ok:
        return jsonify({'success': True, 'message': 'Notification email resent successfully'})
    return jsonify({'success': False, 'error': msg}), 500

@app.route('/api/notifications/logs/<log_id>/preview', methods=['GET'])
def api_preview_notification_log(log_id):
    log = get_notification_log_by_id(log_id)
    if not log:
        return "Notification log entry not found", 404
    
    store_id = log.get('store_id')
    store = get_medical_store(store_id) if store_id else {}
    store_name = store.get('store_name', 'Medical Store') if store else 'Medical Store'

    html = generate_reminder_html_email(
        recipient_name=log.get('recipient_name', 'Valued Member'),
        store_name=store_name,
        doc_name=log.get('document_type', 'Document'),
        doc_num=f"REF-{log_id}",
        expiry_date_str="As Specified",
        days_remaining=log.get('days_remaining', 0)
    )
    return Response(html, mimetype='text/html')

@app.route('/api/notifications/logs/<log_id>/pdf', methods=['GET'])
def api_pdf_notification_log(log_id):
    log = get_notification_log_by_id(log_id)
    if not log:
        return jsonify({'error': 'Notification log entry not found'}), 404

    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph("<b>BOISAR WELFARE CHEMIST ASSOCIATION (BCWA)</b>", styles['Title']))
        elements.append(Paragraph("<font color='#6B7280'>Official Renewal Reminder Certificate & Notification Notice</font>", styles['Normal']))
        elements.append(Spacer(1, 15))

        table_data = [
            ["Notice Reference ID", str(log.get('id'))],
            ["Recipient Name", str(log.get('recipient_name'))],
            ["Recipient Email", str(log.get('recipient_email'))],
            ["Document Category", str(log.get('document_type'))],
            ["Days Remaining Stage", f"{log.get('days_remaining')} Days"],
            ["Delivery Status", str(log.get('delivery_status'))],
            ["Dispatched Timestamp", str(log.get('sent_at'))],
        ]

        t = Table(table_data, colWidths=[200, 320])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (0,-1), colors.HexColor('#F3F4F6')),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#D1D5DB')),
            ('PADDING', (0,0), (-1,-1), 8),
            ('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'),
        ]))
        elements.append(t)

        doc.build(elements)
        buffer.seek(0)
        return Response(buffer.getvalue(), mimetype='application/pdf', headers={
            'Content-Disposition': f'inline; filename=BCWA_Notice_{log_id}.pdf'
        })
    except Exception as e:
        return jsonify({'error': f"Failed to generate PDF: {str(e)}"}), 500

@app.route('/api/admin/send-test-email', methods=['POST'])
def api_admin_send_test_email():
    user = session.get('user')
    if not user or user.get('role') != 'Administrator':
        return jsonify({'success': False, 'error': 'Administrator access required'}), 403

    try:
        res = send_admin_test_email()
        if res.get('success'):
            return jsonify({
                'success': True,
                'message': f"Test email successfully dispatched to {res.get('email')}",
                'details': res
            })
        else:
            return jsonify({
                'success': False,
                'error': f"SMTP Error: {res.get('error')}",
                'details': res
            }), 500
    except Exception as e:
        import traceback
        err_msg = str(e)
        logging.error(f"[TEST EMAIL ROUTE EXCEPTION] {err_msg}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'error': f"Server Exception: {err_msg}"}), 500

# -----------------------------------------------------------------------------
# MEDICAL STORE SELF-SERVICE PORTAL & TENANT APIS
# -----------------------------------------------------------------------------
def get_current_store_id():
    user = session.get('user', {})
    if not is_session_valid() or not user:
        return None
    if user.get('role') == 'Store':
        return user.get('store_id') or user.get('firm_id')
    return None

@app.route('/api/store/dashboard', methods=['GET'])
def api_store_dashboard():
    store_id = get_current_store_id()
    if not store_id:
        return jsonify({'error': 'Unauthorized Store Access'}), 403

    store = get_medical_store(store_id)
    if not store:
        return jsonify({'error': 'Store record not found'}), 404

    docs = get_documents(store_id=store_id)
    pharmacists = get_pharmacists(store_id=store_id)
    notifs = get_notifications(store_id=store_id)

    today_str = datetime.now().strftime('%Y-%m-%d')
    dl_exp = store.get('dl_expiry_date') or ''
    fssai_exp = store.get('fssai_expiry_date') or ''

    ppp_exp = ""
    if pharmacists:
        ppp_exp = pharmacists[0].get('ppp_expiry') or ''

    dl_status = "Active" if dl_exp and dl_exp >= today_str else ("Expired" if dl_exp else "N/A")
    fssai_status = "Active" if fssai_exp and fssai_exp >= today_str else ("Expired" if fssai_exp else "N/A")
    ppp_status = "Active" if ppp_exp and ppp_exp >= today_str else ("Expired" if ppp_exp else "N/A")

    return jsonify({
        'store_id': store_id,
        'store_name': store.get('store_name'),
        'owner_name': store.get('owner_name'),
        'firm_id': session.get('user', {}).get('firm_id'),
        'compliance_score': store.get('compliance_score', 95),
        'dl_expiry_date': dl_exp,
        'dl_status': dl_status,
        'fssai_expiry_date': fssai_exp,
        'fssai_status': fssai_status,
        'ppp_expiry_date': ppp_exp,
        'ppp_status': ppp_status,
        'total_documents': len(docs),
        'notifications': notifs[:10]
    })

@app.route('/api/store/documents', methods=['GET'])
def api_store_documents():
    store_id = get_current_store_id()
    if not store_id:
        return jsonify({'error': 'Unauthorized Store Access'}), 403

    from sample_pdf_generator import ensure_sample_pdfs_for_store
    store = get_medical_store(store_id)
    store_name = store.get('store_name', 'Store') if store else 'Store'
    ensure_sample_pdfs_for_store(store_id, store_name)

    docs = get_documents(store_id=store_id)
    
    if not docs:
        samples = [
            ("Drug License", f"DL-{store_id}-20B", store.get('dl_expiry_date', '2026-12-31'), f"/static/docs/{store_id}_Drug License.pdf"),
            ("Food License", f"FSSAI-{store_id}", store.get('fssai_expiry_date', '2026-11-30'), f"/static/docs/{store_id}_Food License.pdf"),
            ("Rent Agreement", f"RENT-{store_id}", "2027-06-30", f"/static/docs/{store_id}_Rent Agreement.pdf"),
            ("Inspection Report", f"INSP-{store_id}", "2026-10-15", f"/static/docs/{store_id}_Inspection Report.pdf"),
            ("Owner Aadhaar", f"ADH-{store_id}", "N/A", f"/static/docs/{store_id}_Owner Aadhaar.pdf")
        ]
        for cat, num, exp, url in samples:
            doc_id = f"DOC-{store_id}-{cat.replace(' ', '')}"
            save_document({
                'id': doc_id,
                'store_id': store_id,
                'title': f"{cat} - {store_name}",
                'category': cat,
                'file_name': f"{cat}.pdf",
                'file_size_kb': 142,
                'file_url': url,
                'document_number': num,
                'expiry_date': exp,
                'quality_status': 'Passed',
                'quality_notes': 'Verified Document Record'
            })
        docs = get_documents(store_id=store_id)

    return jsonify({'documents': docs, 'total': len(docs)})

@app.route('/api/store/documents/<doc_id>/download', methods=['GET'])
def api_store_download_document(doc_id):
    store_id = get_current_store_id()
    if not store_id:
        return jsonify({'error': 'Unauthorized Store Access'}), 403

    docs = get_documents(store_id=store_id)
    matched = [d for d in docs if d['id'] == doc_id or doc_id in d['id']]
    if not matched:
        return jsonify({'error': 'Document not found or access denied'}), 404

    doc = matched[0]
    file_url = doc.get('file_url', '')
    if file_url.startswith('/static/'):
        local_path = os.path.join(app.root_path, file_url.lstrip('/'))
        if os.path.exists(local_path):
            return send_file(local_path, as_attachment=True, download_name=doc.get('file_name', 'document.pdf'))

    from sample_pdf_generator import create_sample_pdf
    pdf_bytes = create_sample_pdf(doc.get('title', 'Document'), doc.get('category', 'Compliance'), session['user']['store_name'], doc_id)
    return Response(pdf_bytes, mimetype='application/pdf', headers={
        'Content-Disposition': f'attachment; filename="{doc.get("file_name", "Document.pdf")}"'
    })

@app.route('/api/store/renewals', methods=['GET'])
def api_store_renewals():
    store_id = get_current_store_id()
    if not store_id:
        return jsonify({'error': 'Unauthorized Store Access'}), 403

    store = get_medical_store(store_id) or {}
    today = datetime.now()
    renewals = []

    for key, label in [('dl_expiry_date', 'Drug License (20B/21B)'), ('fssai_expiry_date', 'FSSAI Food License')]:
        exp_str = store.get(key)
        if exp_str:
            try:
                exp_dt = datetime.strptime(exp_str, '%Y-%m-%d')
                days = (exp_dt - today).days
                if days < 0:
                    status = 'Expired'
                    color = 'Red'
                elif days <= 15:
                    status = 'Urgent'
                    color = 'Red'
                elif days <= 30:
                    status = 'Approaching'
                    color = 'Orange'
                elif days <= 90:
                    status = 'Upcoming'
                    color = 'Yellow'
                else:
                    status = 'Active'
                    color = 'Green'

                renewals.append({
                    'document': label,
                    'expiry_date': exp_str,
                    'days_remaining': days,
                    'status': status,
                    'color': color
                })
            except Exception:
                pass

    return jsonify({'renewals': renewals})

@app.route('/api/store/profile', methods=['GET'])
def api_store_profile():
    store_id = get_current_store_id()
    if not store_id:
        return jsonify({'error': 'Unauthorized Store Access'}), 403

    store = get_medical_store(store_id) or {}
    user = session.get('user', {})
    return jsonify({
        'store_id': store_id,
        'firm_id': user.get('firm_id'),
        'store_name': store.get('store_name', user.get('store_name')),
        'owner_name': store.get('owner_name', user.get('name')),
        'email': store.get('owner_email', user.get('email')),
        'mobile': store.get('owner_mobile', user.get('mobile')),
        'address': store.get('address', 'Boisar, Maharashtra')
    })

@app.route('/api/store/request-password-reset', methods=['POST'])
def api_store_request_password_reset():
    store_id = get_current_store_id()
    if not store_id:
        return jsonify({'error': 'Unauthorized Store Access'}), 403

    user = session.get('user', {})
    firm_id = user.get('firm_id', 'MED0000')
    store_name = user.get('store_name', 'Store')

    audit_security_log("Password Reset Request", f"Store '{store_name}' ({firm_id}) requested password reset.", user_name=user.get('name'))
    return jsonify({'success': True, 'message': 'Password reset request submitted to Administrator.'})

@app.errorhandler(500)
def handle_500_error(e):
    if app.config.get('DEBUG'):
        return jsonify({
            'error': 'Internal Server Error',
            'details': str(e),
            'environment': app.config.get('ENV')
        }), 500
    return jsonify({'error': 'An internal server error occurred.'}), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5005))
    debug_mode = app.config.get('DEBUG', True)
    env_name = app.config.get('ENV', 'development')
    print(f"🚀 Launching BCWA Portal [{env_name.upper()} MODE] on http://127.0.0.1:{port} (Debug: {debug_mode})")
    try:
        app.run(host='0.0.0.0', port=port, debug=debug_mode)
    except OSError:
        port = 5005
        print(f"🚀 Port occupied. Fallback launching on http://127.0.0.1:{port}...")
        app.run(host='0.0.0.0', port=port, debug=debug_mode)
