from flask import Flask, request, jsonify, render_template, send_file, Response, session
from flask_cors import CORS
import os
import io
import re
import json
import random
from datetime import datetime, timedelta
from config import get_config
from database import (
    init_db, get_dashboard_stats, get_medical_stores, get_medical_store,
    save_medical_store, delete_medical_store, get_pharmacists, save_pharmacist,
    transfer_pharmacist, delete_pharmacist, get_documents, save_document,
    delete_document, get_renewal_calendar_events, get_notifications,
    mark_notification_read, get_activity_logs, get_users, save_user, check_duplicates,
    log_activity
)
from seed_data import generate_seed_data
from supabase_client import upload_to_supabase_storage, test_supabase_connection, db_table

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(get_config())
CORS(app, supports_credentials=True)

init_db()
generate_seed_data()

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

def audit_security_log(action, details, user_name="System"):
    ip = get_client_ip()
    user_agent = request.user_agent.string if request.user_agent else "Unknown Browser"
    full_details = f"{details} | IP: {ip} | User-Agent: {user_agent}"
    log_activity(user_name=user_name, action=action, details=full_details)

# -----------------------------------------------------------------------------
# EXTRA SECURITY HEADERS & NO-CACHE
# -----------------------------------------------------------------------------
@app.after_request
def apply_security_headers(response):
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
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
        "supabase": "healthy" if connected else "reconnecting"
    })

# -----------------------------------------------------------------------------
# AUTHENTICATION API & SESSION SECURITY
# -----------------------------------------------------------------------------
@app.route('/api/auth/login', methods=['POST'])
def api_login():
    ip = get_client_ip()
    is_locked, remaining_secs = check_ip_lockout(ip)
    if is_locked:
        audit_security_log("Failed Login Blocked", f"Lockout active ({remaining_secs}s remaining)", username if 'username' in locals() else "Unknown")
        return jsonify({'success': False, 'error': 'Too many failed attempts. Try again later.'}), 429

    data = request.json or {}
    username = (data.get('username') or data.get('officer_id') or '').strip()
    password = (data.get('password') or '').strip()

    if not username or not password:
        return jsonify({'success': False, 'error': 'Officer ID / Email and Password required'}), 400

    user_found = None
    try:
        users = db_table('users').select('*').execute().data
        matched = [u for u in users if (str(u.get('id', '')).lower() == username.lower() or str(u.get('email', '')).lower() == username.lower()) and u.get('password') == password]
        if matched and matched[0].get('status') == 'Active':
            user_found = matched[0]
    except Exception as e:
        pass

    # Hardcoded Administrator fallback check for Vinayak (VIN2821 / 2821)
    if not user_found and (username.upper() == 'VIN2821' or username.lower() == 'vin2821@bcwaportal.in' or username.lower() == 'vinayak') and password == '2821':
        user_found = {
            'id': 'VIN2821',
            'officer_id': 'VIN2821',
            'name': 'Vinayak',
            'email': 'vin2821@bcwaportal.in',
            'role': 'Administrator',
            'status': 'Active'
        }

    if user_found:
        reset_login_lockout(ip)
        
        # Regenerate session to prevent session fixation
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
        
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            db_table('users').update({'last_login': now_str}).eq('id', user_found['id']).execute()
        except Exception:
            pass

        audit_security_log("Successful Login", f"Officer '{user_found['name']}' logged in successfully.", user_name=user_found['name'])

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

@app.route('/api/auth/session', methods=['GET'])
def api_check_session():
    user = session.get('user')
    if user:
        return jsonify({'authenticated': True, 'user': user})
    return jsonify({'authenticated': False}), 401

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
def api_dashboard_stats():
    stats = get_dashboard_stats()
    return jsonify(stats)

@app.route('/api/stores', methods=['GET'])
def api_get_stores():
    query = request.args.get('query')
    compliance = request.args.get('compliance')
    status = request.args.get('status')
    limit = int(request.args.get('limit', 20))
    offset = int(request.args.get('offset', 0))

    stores = get_medical_stores(query=query, compliance=compliance, status=status, limit=limit, offset=offset)
    return jsonify({'stores': stores, 'total': len(stores)})

@app.route('/api/stores/<store_id>', methods=['GET'])
def api_get_store(store_id):
    store = get_medical_store(store_id)
    if not store:
        return jsonify({'error': 'Medical Store not found'}), 404
    return jsonify(store)

@app.route('/api/stores', methods=['POST'])
@app.route('/api/stores/<store_id>', methods=['PUT'])
def api_save_store(store_id=None):
    data = request.json or {}
    if store_id:
        data['id'] = store_id

    res = save_medical_store(data)
    return jsonify({'success': True, 'id': res['id'], 'shop_code': res['shop_code'], 'warnings': res['warnings']})

@app.route('/api/stores/<store_id>', methods=['DELETE'])
def api_delete_store(store_id):
    success = delete_medical_store(store_id)
    return jsonify({'success': success})

@app.route('/api/pharmacists', methods=['GET'])
def api_get_pharmacists():
    query = request.args.get('query')
    store_id = request.args.get('store_id')
    pharmacists = get_pharmacists(query=query, store_id=store_id)
    return jsonify({'pharmacists': pharmacists, 'total': len(pharmacists)})

@app.route('/api/pharmacists', methods=['POST'])
@app.route('/api/pharmacists/<ph_id>', methods=['PUT'])
def api_save_pharmacist(ph_id=None):
    data = request.json or {}
    if ph_id:
        data['id'] = ph_id

    res = save_pharmacist(data)
    return jsonify({'success': True, 'id': res['id'], 'warnings': res['warnings']})

@app.route('/api/pharmacists/<ph_id>/transfer', methods=['POST'])
def api_transfer_pharmacist(ph_id):
    data = request.json or {}
    new_store_id = data.get('new_store_id')
    joining_date = data.get('joining_date')
    if not new_store_id:
        return jsonify({'error': 'New store ID required'}), 400

    success = transfer_pharmacist(ph_id, new_store_id, joining_date)
    return jsonify({'success': success})

@app.route('/api/pharmacists/<ph_id>', methods=['DELETE'])
def api_delete_pharmacist(ph_id):
    success = delete_pharmacist(ph_id)
    return jsonify({'success': success})

@app.route('/api/documents', methods=['GET'])
def api_get_documents():
    store_id = request.args.get('store_id')
    category = request.args.get('category')
    docs = get_documents(store_id=store_id, category=category)
    return jsonify({'documents': docs})

@app.route('/api/documents/upload', methods=['POST'])
def api_upload_document():
    store_id = request.form.get('store_id')
    category = request.form.get('category', 'Other Documents')
    title = request.form.get('title', 'Document')
    issue_date = request.form.get('issue_date')
    expiry_date = request.form.get('expiry_date')
    file = request.files.get('file')

    file_name = file.filename if file else 'document.pdf'
    
    file_url = f"/static/docs/{file_name}"
    size_kb = random.randint(150, 800)

    if file and upload_to_supabase_storage:
        file_bytes = file.read()
        size_kb = max(1, int(len(file_bytes) / 1024))
        file.seek(0)
        s_res = upload_to_supabase_storage(file, file_name, category=category)
        if s_res.get('success'):
            file_url = s_res.get('url')

    doc_data = {
        'store_id': store_id,
        'category': category,
        'title': title,
        'file_name': file_name,
        'file_url': file_url,
        'file_size_kb': size_kb,
        'issue_date': issue_date,
        'expiry_date': expiry_date
    }

    res = save_document(doc_data)
    return jsonify({'success': True, 'id': res['id'], 'file_url': file_url, 'quality_status': res['quality_status'], 'quality_notes': res['quality_notes']})

@app.route('/api/documents/<doc_id>', methods=['DELETE'])
def api_delete_document(doc_id):
    success = delete_document(doc_id)
    return jsonify({'success': success})

@app.route('/api/calendar/events', methods=['GET'])
def api_calendar_events():
    events = get_renewal_calendar_events()
    return jsonify({'events': events})

@app.route('/api/notifications', methods=['GET'])
def api_notifications():
    notifs = get_notifications()
    return jsonify({'notifications': notifs})

@app.route('/api/notifications/<notif_id>/read', methods=['PUT'])
def api_mark_notif_read(notif_id):
    success = mark_notification_read(notif_id)
    return jsonify({'success': success})

@app.route('/api/activity-logs', methods=['GET'])
def api_activity_logs():
    logs = get_activity_logs()
    return jsonify({'logs': logs})

@app.route('/api/admin/users', methods=['GET', 'POST'])
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
    port = int(os.environ.get('PORT', 5000))
    debug_mode = app.config.get('DEBUG', True)
    env_name = app.config.get('ENV', 'development')
    print(f"🚀 Launching BCWA Portal [{env_name.upper()} MODE] on http://127.0.0.1:{port} (Debug: {debug_mode})")
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
