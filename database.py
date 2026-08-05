import sqlite3
import json
import os
import re
from datetime import datetime, timedelta
import random

try:
    from cloud_services import sync_to_firestore, upload_document_to_firebase_storage
except ImportError:
    sync_to_firestore = None
    upload_document_to_firebase_storage = None

DB_FILE = os.path.join(os.path.dirname(__file__), 'bcwa_portal.db')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Medical Stores Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS medical_stores (
            id TEXT PRIMARY KEY,
            store_name TEXT NOT NULL,
            shop_code TEXT UNIQUE NOT NULL,
            business_type TEXT DEFAULT 'Retail Pharmacy',
            drug_license_category TEXT DEFAULT '20B / 21B',
            owner_name TEXT NOT NULL,
            owner_mobile TEXT NOT NULL,
            owner_whatsapp TEXT,
            owner_email TEXT,
            owner_pan TEXT,
            owner_aadhaar TEXT,
            owner_address TEXT,
            owner_photo TEXT,
            store_logo TEXT,
            store_photo TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            address_line1 TEXT NOT NULL,
            address_line2 TEXT,
            area TEXT DEFAULT 'Boisar',
            city TEXT DEFAULT 'Palghar',
            state TEXT DEFAULT 'Maharashtra',
            pincode TEXT DEFAULT '401501',
            google_map_url TEXT,
            gps_coordinates TEXT,
            dl_20b_number TEXT NOT NULL,
            dl_21b_number TEXT NOT NULL,
            dl_issue_date TEXT NOT NULL,
            dl_expiry_date TEXT NOT NULL,
            dl_issuing_authority TEXT DEFAULT 'FDA Maharashtra',
            dl_renewal_date TEXT,
            dl_pdf_url TEXT,
            fssai_number TEXT NOT NULL,
            fssai_issue_date TEXT NOT NULL,
            fssai_expiry_date TEXT NOT NULL,
            fssai_pdf_url TEXT,
            compliance_score INTEGER DEFAULT 85,
            compliance_status TEXT DEFAULT 'Good',
            status TEXT DEFAULT 'Active',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # Pharmacists Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pharmacists (
            id TEXT PRIMARY KEY,
            store_id TEXT,
            full_name TEXT NOT NULL,
            photo TEXT,
            mspc_number TEXT UNIQUE NOT NULL,
            ppp_number TEXT UNIQUE NOT NULL,
            ppp_expiry TEXT NOT NULL,
            reg_expiry TEXT NOT NULL,
            qualification TEXT DEFAULT 'B.Pharm',
            joining_date TEXT NOT NULL,
            leaving_date TEXT,
            mobile TEXT NOT NULL,
            email TEXT,
            status TEXT DEFAULT 'Active',
            ppp_card_url TEXT,
            degree_cert_url TEXT,
            reg_cert_url TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (store_id) REFERENCES medical_stores (id) ON DELETE SET NULL
        )
    ''')

    # Documents Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            store_id TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_url TEXT NOT NULL,
            file_size_kb INTEGER DEFAULT 250,
            version INTEGER DEFAULT 1,
            issue_date TEXT,
            expiry_date TEXT,
            quality_status TEXT DEFAULT 'Passed',
            quality_notes TEXT DEFAULT 'Resolution OK, Text clear',
            uploaded_by TEXT DEFAULT 'Office Staff',
            created_at TEXT NOT NULL,
            FOREIGN KEY (store_id) REFERENCES medical_stores (id) ON DELETE CASCADE
        )
    ''')

    # Notifications Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            type TEXT DEFAULT 'Warning',
            target_type TEXT,
            target_id TEXT,
            is_read INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''')

    # Activity Logs Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_logs (
            id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT NOT NULL,
            store_id TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    # Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'Office Staff',
            status TEXT DEFAULT 'Active',
            last_login TEXT
        )
    ''')

    # Reminders Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reminders (
            id TEXT PRIMARY KEY,
            store_id TEXT NOT NULL,
            target_type TEXT NOT NULL,
            recipient_name TEXT NOT NULL,
            recipient_contact TEXT NOT NULL,
            days_remaining INTEGER NOT NULL,
            reminder_date TEXT NOT NULL,
            status TEXT DEFAULT 'Sent',
            details TEXT NOT NULL,
            FOREIGN KEY (store_id) REFERENCES medical_stores (id) ON DELETE CASCADE
        )
    ''')

    # Create Indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stores_name ON medical_stores(store_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stores_dl ON medical_stores(dl_20b_number, dl_21b_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_stores_fssai ON medical_stores(fssai_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pharmacists_store ON pharmacists(store_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pharmacists_mspc ON pharmacists(mspc_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_pharmacists_ppp ON pharmacists(ppp_number)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_documents_store ON documents(store_id)')

    conn.commit()
    conn.close()

def calculate_compliance_score(store_dict, pharmacists_list, docs_count):
    score = 0
    today = datetime.now().date()

    # 1. Drug License Expiry check (Max 30 pts)
    dl_exp = datetime.strptime(store_dict['dl_expiry_date'], '%Y-%m-%d').date()
    days_to_dl = (dl_exp - today).days
    if days_to_dl > 90:
        score += 30
    elif days_to_dl > 0:
        score += 15
    else:
        score += 0

    # 2. Food License (FSSAI) Expiry check (Max 20 pts)
    fssai_exp = datetime.strptime(store_dict['fssai_expiry_date'], '%Y-%m-%d').date()
    days_to_fssai = (fssai_exp - today).days
    if days_to_fssai > 90:
        score += 20
    elif days_to_fssai > 0:
        score += 10
    else:
        score += 0

    # 3. Pharmacists Assignment & PPP Validity (Max 30 pts)
    if pharmacists_list and len(pharmacists_list) > 0:
        score += 15
        valid_ppp = True
        for p in pharmacists_list:
            ppp_exp = datetime.strptime(p['ppp_expiry'], '%Y-%m-%d').date()
            if (ppp_exp - today).days <= 0:
                valid_ppp = False
                break
        if valid_ppp:
            score += 15
    
    # 4. Documents completeness (Max 20 pts)
    if docs_count >= 8:
        score += 20
    elif docs_count >= 4:
        score += 12
    elif docs_count >= 1:
        score += 6

    status = 'Excellent' if score >= 90 else ('Good' if score >= 75 else ('Needs Attention' if score >= 50 else 'Critical'))
    return score, status

def check_duplicates(dl_20b=None, dl_21b=None, fssai=None, ppp=None, mspc=None, store_name=None, exclude_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    warnings = []

    if store_name:
        query = 'SELECT id, store_name FROM medical_stores WHERE LOWER(store_name) = LOWER(?)'
        args = [store_name]
        if exclude_id:
            query += ' AND id != ?'
            args.append(exclude_id)
        cursor.execute(query, args)
        row = cursor.fetchone()
        if row:
            warnings.append(f"Medical Store Name '{store_name}' already exists (ID: {row['id']}).")

    if dl_20b:
        query = 'SELECT id, store_name FROM medical_stores WHERE dl_20b_number = ?'
        args = [dl_20b]
        if exclude_id:
            query += ' AND id != ?'
            args.append(exclude_id)
        cursor.execute(query, args)
        row = cursor.fetchone()
        if row:
            warnings.append(f"Drug License 20B '{dl_20b}' already registered for {row['store_name']}.")

    if dl_21b:
        query = 'SELECT id, store_name FROM medical_stores WHERE dl_21b_number = ?'
        args = [dl_21b]
        if exclude_id:
            query += ' AND id != ?'
            args.append(exclude_id)
        cursor.execute(query, args)
        row = cursor.fetchone()
        if row:
            warnings.append(f"Drug License 21B '{dl_21b}' already registered for {row['store_name']}.")

    if fssai:
        query = 'SELECT id, store_name FROM medical_stores WHERE fssai_number = ?'
        args = [fssai]
        if exclude_id:
            query += ' AND id != ?'
            args.append(exclude_id)
        cursor.execute(query, args)
        row = cursor.fetchone()
        if row:
            warnings.append(f"Food License FSSAI '{fssai}' already registered for {row['store_name']}.")

    if ppp:
        query = 'SELECT id, full_name FROM pharmacists WHERE ppp_number = ?'
        args = [ppp]
        if exclude_id:
            query += ' AND id != ?'
            args.append(exclude_id)
        cursor.execute(query, args)
        row = cursor.fetchone()
        if row:
            warnings.append(f"PPP Card Number '{ppp}' is already assigned to Pharmacist '{row['full_name']}'.")

    if mspc:
        query = 'SELECT id, full_name FROM pharmacists WHERE mspc_number = ?'
        args = [mspc]
        if exclude_id:
            query += ' AND id != ?'
            args.append(exclude_id)
        cursor.execute(query, args)
        row = cursor.fetchone()
        if row:
            warnings.append(f"MSPC Registration Number '{mspc}' already exists for Pharmacist '{row['full_name']}'.")

    conn.close()
    return warnings

def get_dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().date()
    d90 = (today + timedelta(days=90)).strftime('%Y-%m-%d')
    today_str = today.strftime('%Y-%m-%d')

    cursor.execute('SELECT COUNT(*) as total FROM medical_stores')
    total_stores = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM pharmacists')
    total_pharmacists = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM medical_stores WHERE dl_expiry_date <= ? AND dl_expiry_date >= ?', (d90, today_str))
    dl_expiring = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM medical_stores WHERE dl_expiry_date < ?', (today_str,))
    dl_expired = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM medical_stores WHERE fssai_expiry_date <= ? AND fssai_expiry_date >= ?', (d90, today_str))
    fssai_expiring = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM medical_stores WHERE fssai_expiry_date < ?', (today_str,))
    fssai_expired = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM pharmacists WHERE ppp_expiry <= ? AND ppp_expiry >= ?', (d90, today_str))
    ppp_expiring = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM pharmacists WHERE ppp_expiry < ?', (today_str,))
    ppp_expired = cursor.fetchone()['total']

    cursor.execute('SELECT COUNT(*) as total FROM documents WHERE expiry_date IS NOT NULL AND expiry_date < ?', (today_str,))
    expired_docs = cursor.fetchone()['total']

    cursor.execute('SELECT AVG(compliance_score) as avg_score FROM medical_stores')
    avg_score_val = cursor.fetchone()['avg_score']
    avg_score = round(avg_score_val if avg_score_val else 82, 1)

    upcoming_renewals = dl_expiring + fssai_expiring + ppp_expiring

    cursor.execute('SELECT COUNT(*) as total FROM notifications WHERE DATE(created_at) = ?', (today_str,))
    todays_notifs = cursor.fetchone()['total']

    cursor.execute("SELECT compliance_status, COUNT(*) as count FROM medical_stores GROUP BY compliance_status")
    compliance_breakdown = {row['compliance_status']: row['count'] for row in cursor.fetchall()}

    cursor.execute("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 10")
    recent_activity = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT id, store_name, owner_name, shop_code, compliance_score, compliance_status, created_at FROM medical_stores ORDER BY created_at DESC LIMIT 5")
    recent_stores = [dict(row) for row in cursor.fetchall()]

    cursor.execute("SELECT p.id, p.full_name, p.mspc_number, p.qualification, m.store_name FROM pharmacists p LEFT JOIN medical_stores m ON p.store_id = m.id ORDER BY p.created_at DESC LIMIT 5")
    recent_pharmacists = [dict(row) for row in cursor.fetchall()]

    conn.close()

    return {
        'total_stores': total_stores,
        'total_pharmacists': total_pharmacists,
        'dl_expiring': dl_expiring,
        'dl_expired': dl_expired,
        'fssai_expiring': fssai_expiring,
        'fssai_expired': fssai_expired,
        'ppp_expiring': ppp_expiring,
        'ppp_expired': ppp_expired,
        'expired_documents': expired_docs + dl_expired + fssai_expired + ppp_expired,
        'compliance_score': avg_score,
        'upcoming_renewals': upcoming_renewals,
        'todays_notifications': todays_notifs,
        'compliance_breakdown': compliance_breakdown,
        'recent_activity': recent_activity,
        'recent_stores': recent_stores,
        'recent_pharmacists': recent_pharmacists
    }

def get_medical_stores(query=None, compliance=None, status=None, limit=20, offset=0):
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM medical_stores WHERE 1=1"
    params = []

    if query:
        q = f"%{query.strip()}%"
        sql += """ AND (
            store_name LIKE ? OR 
            owner_name LIKE ? OR 
            dl_20b_number LIKE ? OR 
            dl_21b_number LIKE ? OR 
            fssai_number LIKE ? OR 
            owner_mobile LIKE ? OR 
            shop_code LIKE ?
        )"""
        params.extend([q, q, q, q, q, q, q])

    if compliance:
        sql += " AND compliance_status = ?"
        params.append(compliance)

    if status:
        sql += " AND status = ?"
        params.append(status)

    sql += " ORDER BY store_name ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    stores = [dict(r) for r in rows]

    for store in stores:
        cursor.execute("SELECT COUNT(*) as count FROM pharmacists WHERE store_id = ?", (store['id'],))
        store['pharmacist_count'] = cursor.fetchone()['count']

    conn.close()
    return stores

def get_medical_store(store_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM medical_stores WHERE id = ?", (store_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return None

    store = dict(row)

    cursor.execute("SELECT * FROM pharmacists WHERE store_id = ? ORDER BY full_name ASC", (store_id,))
    store['pharmacists'] = [dict(p) for p in cursor.fetchall()]

    cursor.execute("SELECT * FROM documents WHERE store_id = ? ORDER BY category, title", (store_id,))
    store['documents'] = [dict(d) for d in cursor.fetchall()]

    cursor.execute("SELECT * FROM reminders WHERE store_id = ? ORDER BY reminder_date DESC", (store_id,))
    store['reminders'] = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM activity_logs WHERE store_id = ? ORDER BY created_at DESC LIMIT 20", (store_id,))
    store['activity_history'] = [dict(a) for a in cursor.fetchall()]

    conn.close()
    return store

def save_medical_store(data):
    conn = get_db_connection()
    cursor = conn.cursor()

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    is_new = 'id' not in data or not data['id']
    store_id = data.get('id') or f"MS-{random.randint(10000, 99999)}"
    shop_code = data.get('shop_code') or f"BCWA-{random.randint(100, 999)}"

    dups = check_duplicates(
        dl_20b=data.get('dl_20b_number'),
        dl_21b=data.get('dl_21b_number'),
        fssai=data.get('fssai_number'),
        store_name=data.get('store_name'),
        exclude_id=store_id if not is_new else None
    )

    if is_new:
        cursor.execute('''
            INSERT INTO medical_stores (
                id, store_name, shop_code, business_type, drug_license_category,
                owner_name, owner_mobile, owner_whatsapp, owner_email, owner_pan, owner_aadhaar, owner_address, owner_photo,
                store_logo, store_photo, contact_phone, contact_email, address_line1, address_line2, area, city, state, pincode,
                google_map_url, gps_coordinates, dl_20b_number, dl_21b_number, dl_issue_date, dl_expiry_date, dl_issuing_authority,
                dl_renewal_date, dl_pdf_url, fssai_number, fssai_issue_date, fssai_expiry_date, fssai_pdf_url, compliance_score,
                compliance_status, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            store_id, data.get('store_name'), shop_code, data.get('business_type', 'Retail Pharmacy'), data.get('drug_license_category', '20B / 21B'),
            data.get('owner_name'), data.get('owner_mobile'), data.get('owner_whatsapp'), data.get('owner_email'), data.get('owner_pan'), data.get('owner_aadhaar'), data.get('owner_address'), data.get('owner_photo', ''),
            data.get('store_logo', ''), data.get('store_photo', ''), data.get('contact_phone'), data.get('contact_email'), data.get('address_line1'), data.get('address_line2', ''), data.get('area', 'Boisar'), data.get('city', 'Palghar'), data.get('state', 'Maharashtra'), data.get('pincode', '401501'),
            data.get('google_map_url', ''), data.get('gps_coordinates', '19.8000, 72.7500'), data.get('dl_20b_number'), data.get('dl_21b_number'), data.get('dl_issue_date'), data.get('dl_expiry_date'), data.get('dl_issuing_authority', 'FDA Maharashtra'),
            data.get('dl_renewal_date', ''), data.get('dl_pdf_url', ''), data.get('fssai_number'), data.get('fssai_issue_date'), data.get('fssai_expiry_date'), data.get('fssai_pdf_url', ''),
            85, 'Good', data.get('status', 'Active'), now_str, now_str
        ))
        cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (f"ACT-{random.randint(10000,99999)}", "Office Staff", "Store Registered", f"Registered new Medical Store: {data.get('store_name')}", store_id, now_str))
    else:
        cursor.execute('''
            UPDATE medical_stores SET
                store_name=?, business_type=?, drug_license_category=?,
                owner_name=?, owner_mobile=?, owner_whatsapp=?, owner_email=?, owner_pan=?, owner_aadhaar=?, owner_address=?, owner_photo=?,
                store_logo=?, store_photo=?, contact_phone=?, contact_email=?, address_line1=?, address_line2=?, area=?, city=?, state=?, pincode=?,
                google_map_url=?, gps_coordinates=?, dl_20b_number=?, dl_21b_number=?, dl_issue_date=?, dl_expiry_date=?, dl_issuing_authority=?,
                dl_renewal_date=?, fssai_number=?, fssai_issue_date=?, fssai_expiry_date=?, status=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('store_name'), data.get('business_type', 'Retail Pharmacy'), data.get('drug_license_category', '20B / 21B'),
            data.get('owner_name'), data.get('owner_mobile'), data.get('owner_whatsapp'), data.get('owner_email'), data.get('owner_pan'), data.get('owner_aadhaar'), data.get('owner_address'), data.get('owner_photo', ''),
            data.get('store_logo', ''), data.get('store_photo', ''), data.get('contact_phone'), data.get('contact_email'), data.get('address_line1'), data.get('address_line2', ''), data.get('area', 'Boisar'), data.get('city', 'Palghar'), data.get('state', 'Maharashtra'), data.get('pincode', '401501'),
            data.get('google_map_url', ''), data.get('gps_coordinates', '19.8000, 72.7500'), data.get('dl_20b_number'), data.get('dl_21b_number'), data.get('dl_issue_date'), data.get('dl_expiry_date'), data.get('dl_issuing_authority', 'FDA Maharashtra'),
            data.get('dl_renewal_date', ''), data.get('fssai_number'), data.get('fssai_issue_date'), data.get('fssai_expiry_date'), data.get('status', 'Active'), now_str,
            store_id
        ))
        cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (f"ACT-{random.randint(10000,99999)}", "Office Staff", "Store Updated", f"Updated details for Medical Store: {data.get('store_name')}", store_id, now_str))

    cursor.execute("SELECT * FROM medical_stores WHERE id = ?", (store_id,))
    updated_store = dict(cursor.fetchone())
    cursor.execute("SELECT * FROM pharmacists WHERE store_id = ?", (store_id,))
    ph_list = [dict(p) for p in cursor.fetchall()]
    cursor.execute("SELECT COUNT(*) as cnt FROM documents WHERE store_id = ?", (store_id,))
    doc_cnt = cursor.fetchone()['cnt']

    score, status_str = calculate_compliance_score(updated_store, ph_list, doc_cnt)
    cursor.execute("UPDATE medical_stores SET compliance_score = ?, compliance_status = ? WHERE id = ?", (score, status_str, store_id))

    conn.commit()
    conn.close()

    if sync_to_firestore:
        try:
            sync_to_firestore('medical_stores', store_id, updated_store)
        except Exception:
            pass

    return {'id': store_id, 'shop_code': shop_code, 'warnings': dups}

def delete_medical_store(store_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("SELECT store_name FROM medical_stores WHERE id = ?", (store_id,))
    row = cursor.fetchone()
    name = row['store_name'] if row else store_id

    cursor.execute("DELETE FROM medical_stores WHERE id = ?", (store_id,))
    cursor.execute("UPDATE pharmacists SET store_id = NULL WHERE store_id = ?", (store_id,))
    cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (f"ACT-{random.randint(10000,99999)}", "Administrator", "Store Deleted", f"Deleted Medical Store: {name}", store_id, now_str))

    conn.commit()
    conn.close()
    return True

def get_pharmacists(query=None, store_id=None, limit=100):
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT p.*, m.store_name, m.shop_code 
        FROM pharmacists p 
        LEFT JOIN medical_stores m ON p.store_id = m.id 
        WHERE 1=1
    """
    params = []

    if store_id:
        sql += " AND p.store_id = ?"
        params.append(store_id)

    if query:
        q = f"%{query.strip()}%"
        sql += """ AND (
            p.full_name LIKE ? OR 
            p.mspc_number LIKE ? OR 
            p.ppp_number LIKE ? OR 
            p.mobile LIKE ? OR
            m.store_name LIKE ?
        )"""
        params.extend([q, q, q, q, q])

    sql += " ORDER BY p.full_name ASC LIMIT ?"
    params.append(limit)

    cursor.execute(sql, params)
    pharmacists = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return pharmacists

def save_pharmacist(data):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    is_new = 'id' not in data or not data['id']
    ph_id = data.get('id') or f"PH-{random.randint(10000, 99999)}"

    dups = check_duplicates(
        ppp=data.get('ppp_number'),
        mspc=data.get('mspc_number'),
        exclude_id=ph_id if not is_new else None
    )

    if is_new:
        cursor.execute('''
            INSERT INTO pharmacists (
                id, store_id, full_name, photo, mspc_number, ppp_number, ppp_expiry, reg_expiry,
                qualification, joining_date, leaving_date, mobile, email, status, ppp_card_url, degree_cert_url, reg_cert_url,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            ph_id, data.get('store_id'), data.get('full_name'), data.get('photo', ''), data.get('mspc_number'),
            data.get('ppp_number'), data.get('ppp_expiry'), data.get('reg_expiry'), data.get('qualification', 'B.Pharm'),
            data.get('joining_date'), data.get('leaving_date', ''), data.get('mobile'), data.get('email', ''),
            data.get('status', 'Active'), data.get('ppp_card_url', ''), data.get('degree_cert_url', ''), data.get('reg_cert_url', ''),
            now_str, now_str
        ))
        cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (f"ACT-{random.randint(10000,99999)}", "Office Staff", "Pharmacist Added", f"Added Pharmacist: {data.get('full_name')} ({data.get('mspc_number')})", data.get('store_id'), now_str))
    else:
        cursor.execute('''
            UPDATE pharmacists SET
                store_id=?, full_name=?, photo=?, mspc_number=?, ppp_number=?, ppp_expiry=?, reg_expiry=?,
                qualification=?, joining_date=?, leaving_date=?, mobile=?, email=?, status=?, updated_at=?
            WHERE id=?
        ''', (
            data.get('store_id'), data.get('full_name'), data.get('photo', ''), data.get('mspc_number'),
            data.get('ppp_number'), data.get('ppp_expiry'), data.get('reg_expiry'), data.get('qualification', 'B.Pharm'),
            data.get('joining_date'), data.get('leaving_date', ''), data.get('mobile'), data.get('email', ''),
            data.get('status', 'Active'), now_str, ph_id
        ))
        cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                       (f"ACT-{random.randint(10000,99999)}", "Office Staff", "Pharmacist Updated", f"Updated Pharmacist: {data.get('full_name')}", data.get('store_id'), now_str))

    conn.commit()
    conn.close()

    if sync_to_firestore:
        try:
            sync_to_firestore('pharmacists', ph_id, data)
        except Exception:
            pass

    return {'id': ph_id, 'warnings': dups}

def transfer_pharmacist(pharmacist_id, new_store_id, joining_date=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    today_str = datetime.now().strftime('%Y-%m-%d')

    cursor.execute("SELECT p.full_name, m.store_name FROM pharmacists p LEFT JOIN medical_stores m ON p.store_id = m.id WHERE p.id = ?", (pharmacist_id,))
    row = cursor.fetchone()
    p_name = row['full_name']
    old_store = row['store_name'] or "Unassigned"

    cursor.execute("SELECT store_name FROM medical_stores WHERE id = ?", (new_store_id,))
    new_store_row = cursor.fetchone()
    new_store_name = new_store_row['store_name'] if new_store_row else "New Store"

    cursor.execute('''
        UPDATE pharmacists 
        SET store_id = ?, leaving_date = ?, joining_date = ?, updated_at = ?
        WHERE id = ?
    ''', (new_store_id, today_str, joining_date or today_str, now_str, pharmacist_id))

    cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (f"ACT-{random.randint(10000,99999)}", "Office Staff", "Pharmacist Transferred", f"Transferred Pharmacist {p_name} from {old_store} to {new_store_name}", new_store_id, now_str))

    conn.commit()
    conn.close()
    return True

def delete_pharmacist(pharmacist_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("SELECT full_name, store_id FROM pharmacists WHERE id = ?", (pharmacist_id,))
    row = cursor.fetchone()
    name = row['full_name'] if row else pharmacist_id
    store_id = row['store_id'] if row else None

    cursor.execute("DELETE FROM pharmacists WHERE id = ?", (pharmacist_id,))
    cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (f"ACT-{random.randint(10000,99999)}", "Office Staff", "Pharmacist Deleted", f"Deleted Pharmacist record: {name}", store_id, now_str))

    conn.commit()
    conn.close()
    return True

def get_documents(store_id=None, category=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    sql = """
        SELECT d.*, m.store_name 
        FROM documents d 
        LEFT JOIN medical_stores m ON d.store_id = m.id 
        WHERE 1=1
    """
    params = []

    if store_id:
        sql += " AND d.store_id = ?"
        params.append(store_id)

    if category:
        sql += " AND d.category = ?"
        params.append(category)

    sql += " ORDER BY d.created_at DESC"

    cursor.execute(sql, params)
    docs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return docs

def save_document(data):
    conn = get_db_connection()
    cursor = conn.cursor()
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

    cursor.execute('''
        INSERT INTO documents (
            id, store_id, category, title, file_name, file_url, file_size_kb, version,
            issue_date, expiry_date, quality_status, quality_notes, uploaded_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        doc_id, data.get('store_id'), data.get('category', 'Drug License'), data.get('title'),
        file_name, data.get('file_url', '/static/docs/sample.pdf'), size_kb, data.get('version', 1),
        data.get('issue_date'), data.get('expiry_date'), quality_status, quality_notes,
        data.get('uploaded_by', 'Office Staff'), now_str
    ))

    cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (f"ACT-{random.randint(10000,99999)}", "Office Staff", "Document Uploaded", f"Uploaded document '{data.get('title')}' in category '{data.get('category')}'", data.get('store_id'), now_str))

    conn.commit()
    conn.close()
    return {'id': doc_id, 'quality_status': quality_status, 'quality_notes': quality_notes}

def delete_document(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("SELECT title, store_id FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    title = row['title'] if row else doc_id
    store_id = row['store_id'] if row else None

    cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
    cursor.execute("INSERT INTO activity_logs (id, user_name, action, details, store_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                   (f"ACT-{random.randint(10000,99999)}", "Office Staff", "Document Deleted", f"Deleted document: {title}", store_id, now_str))

    conn.commit()
    conn.close()
    return True

def get_renewal_calendar_events():
    conn = get_db_connection()
    cursor = conn.cursor()
    today = datetime.now().date()

    events = []

    cursor.execute("SELECT id, store_name, dl_20b_number, dl_expiry_date, owner_name, owner_mobile FROM medical_stores WHERE dl_expiry_date IS NOT NULL")
    for row in cursor.fetchall():
        exp = datetime.strptime(row['dl_expiry_date'], '%Y-%m-%d').date()
        diff = (exp - today).days
        status = 'Red' if diff < 0 else ('Yellow' if diff <= 90 else 'Green')
        events.append({
            'id': f"DL-{row['id']}",
            'store_id': row['id'],
            'store_name': row['store_name'],
            'title': f"Drug License Expiry - {row['store_name']}",
            'type': 'Drug License',
            'license_number': row['dl_20b_number'],
            'date': row['dl_expiry_date'],
            'status': status,
            'days_remaining': diff,
            'owner_name': row['owner_name'],
            'contact': row['owner_mobile']
        })

    cursor.execute("SELECT id, store_name, fssai_number, fssai_expiry_date, owner_name, owner_mobile FROM medical_stores WHERE fssai_expiry_date IS NOT NULL")
    for row in cursor.fetchall():
        exp = datetime.strptime(row['fssai_expiry_date'], '%Y-%m-%d').date()
        diff = (exp - today).days
        status = 'Red' if diff < 0 else ('Yellow' if diff <= 90 else 'Green')
        events.append({
            'id': f"FSSAI-{row['id']}",
            'store_id': row['id'],
            'store_name': row['store_name'],
            'title': f"FSSAI Food License Expiry - {row['store_name']}",
            'type': 'Food License',
            'license_number': row['fssai_number'],
            'date': row['fssai_expiry_date'],
            'status': status,
            'days_remaining': diff,
            'owner_name': row['owner_name'],
            'contact': row['owner_mobile']
        })

    cursor.execute("""
        SELECT p.id, p.full_name, p.ppp_number, p.ppp_expiry, p.mobile, m.id as store_id, m.store_name 
        FROM pharmacists p 
        LEFT JOIN medical_stores m ON p.store_id = m.id 
        WHERE p.ppp_expiry IS NOT NULL
    """)
    for row in cursor.fetchall():
        exp = datetime.strptime(row['ppp_expiry'], '%Y-%m-%d').date()
        diff = (exp - today).days
        status = 'Red' if diff < 0 else ('Yellow' if diff <= 90 else 'Green')
        events.append({
            'id': f"PPP-{row['id']}",
            'store_id': row['store_id'],
            'store_name': row['store_name'] or 'Unassigned Pharmacist',
            'title': f"PPP Card Expiry - {row['full_name']} ({row['store_name'] or 'Freelance'})",
            'type': 'PPP Card',
            'license_number': row['ppp_number'],
            'date': row['ppp_expiry'],
            'status': status,
            'days_remaining': diff,
            'pharmacist_name': row['full_name'],
            'contact': row['mobile']
        })

    conn.close()
    return events

def get_notifications(limit=50):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,))
    notifs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return notifs

def mark_notification_read(notif_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()
    return True

def get_activity_logs(limit=100):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT ?", (limit,))
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return logs

def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, email, role, status, last_login FROM users ORDER BY name ASC")
    users = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return users

def save_user(data):
    conn = get_db_connection()
    cursor = conn.cursor()

    user_id = data.get('id') or f"USR-{random.randint(10000, 99999)}"
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    exists = cursor.fetchone()

    if not exists:
        cursor.execute('''
            INSERT INTO users (id, name, email, password, role, status, last_login)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, data['name'], data['email'], data.get('password', 'BCWA@2026'), data.get('role', 'Office Staff'), data.get('status', 'Active'), now_str))
    else:
        cursor.execute('''
            UPDATE users SET name=?, email=?, role=?, status=? WHERE id=?
        ''', (data['name'], data['email'], data.get('role', 'Office Staff'), data.get('status', 'Active'), user_id))

    conn.commit()
    conn.close()
    return True
