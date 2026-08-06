import random
from datetime import datetime, timedelta
from database import init_db
from supabase_client import db_table
from werkzeug.security import generate_password_hash

STORE_PREFIXES = [
    "Sai", "Shree", "Mahavir", "Boishar Welfare", "Apollo", "MedPlus", "Sanjivani", 
    "Wellness", "Care", "Dhanvantari", "Lifeline", "National", "Shubham", "Om", 
    "Pavan", "Vighnaharta", "Gajanand", "Jai Ambe", "Tarapur", "Palghar"
]

STORE_SUFFIXES = [
    "Chemist & Druggist", "Medical & General Stores", "Pharma", "Medicos", 
    "Health Pharmacy", "Medical Center", "Drug House", "Chemist", "Pharmacy"
]

FIRST_NAMES = [
    "Rajesh", "Amit", "Suresh", "Vijay", "Nitin", "Deepak", "Manoj", "Anil", 
    "Ramesh", "Pravin", "Sunil", "Pankaj", "Vikas", "Mahesh", "Sanjay", "Rahul", 
    "Ashok", "Kiran", "Sachin", "Dinesh", "Ganesh", "Santosh", "Ajay", "Pradeep",
    "Priya", "Neha", "Sneha", "Pooja", "Aarti", "Kavita", "Swati", "Anjali"
]

LAST_NAMES = [
    "Patil", "Shah", "Jain", "Mehta", "Chaudhari", "Gharat", "Thakur", "Singh", 
    "Gupta", "Sharma", "Raut", "More", "Save", "Tamore", "Vartha", "Kadam", 
    "Shinde", "Pawar", "Deshmukh", "Jadhav", "Bhanushali", "Parekh", "Soni"
]

AREAS_BOISAR = [
    "Navapur Road, Boisar West", "Tarapur MIDC, Boisar", "OSTWAL Empire, Boisar East",
    "Boisar Station Road", "Katkar Pada, Boisar", "Mahim Road, Palghar", "Manor Road, Palghar",
    "Kambode, Boisar", "Betegaon, Boisar East", "Pamtembi, Boisar", "Chinchani Road, Tarapur",
    "Pasthal Village, Boisar", "Kolwade Road, Boisar", "Salwad, Boisar"
]

DOC_CATEGORIES = [
    "Drug License", "Food License", "PPP Cards", "Rent Agreement", "Light Bill",
    "Cold Storage Certificate", "Tax Receipt", "Namuna 8", "Owner Aadhaar",
    "Owner PAN", "Store PAN", "Qualification Certificates", "Appointment Letters",
    "Acceptance Letters", "Store Photos", "Other Documents"
]

QUALIFICATIONS = ["B.Pharm", "D.Pharm", "M.Pharm", "Pharm.D"]

def generate_seed_data():
    init_db()

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    today = now.date()

    # 1. Seed Administrator Account (Vinayak VIN2821)
    admin_user = {
        'id': 'VIN2821',
        'name': 'Vinayak',
        'email': 'vin2821@bcwaportal.in',
        'password': generate_password_hash('2821'),
        'role': 'Administrator',
        'status': 'Active',
        'last_login': now_str,
        'created_at': now_str,
        'updated_at': now_str
    }
    db_table('users').insert(admin_user).execute()

    stores_list = []
    pharmacists_list = []
    documents_list = []
    activity_logs = []
    notifications = []
    notif_queue_list = []
    notif_logs_list = []

    # Expiry offset days for 20 stores to cover all target reminder stages:
    # Expired (-10), 1d, 3d, 7d, 10d, 15d, 30d, 60d, 90d, 120d, 180d, 365d, etc.
    stage_offsets = [-10, 1, 3, 7, 10, 15, 30, 60, 90, 120, 180, 240, 365, 400, 500, 600, 700, 14, 45, 730]

    for i in range(1, 21):
        store_id = f"BCWA-MED-{i:06d}"
        firm_id = f"BCWA-MED-{i:06d}"
        shop_code = f"BCWA-BSR-{100 + i}"
        store_name = f"{STORE_PREFIXES[(i-1) % len(STORE_PREFIXES)]} {STORE_SUFFIXES[(i-1) % len(STORE_SUFFIXES)]}"
        owner_name = f"{FIRST_NAMES[(i*2) % len(FIRST_NAMES)]} {LAST_NAMES[(i*3) % len(LAST_NAMES)]}"
        owner_mobile = "8766759824"
        owner_email = "bhosalevinayakwe@gmail.com"
        
        dl_20b = f"MH-TZ4-{100000 + i*4321 % 899999}"
        dl_21b = f"MH-TZ4-{100000 + i*5678 % 899999}"
        fssai_num = f"21524{100000000 + i*9876543 % 899999999}"
        
        offset = stage_offsets[i - 1]
        dl_expiry_date = today + timedelta(days=offset)
        dl_issue_date = dl_expiry_date - timedelta(days=1825)  # 5 years valid
        
        fssai_expiry_date = today + timedelta(days=offset + 10)
        fssai_issue_date = fssai_expiry_date - timedelta(days=1825)

        dl_issue = dl_issue_date.strftime('%Y-%m-%d')
        dl_expiry = dl_expiry_date.strftime('%Y-%m-%d')
        fssai_issue = fssai_issue_date.strftime('%Y-%m-%d')
        fssai_expiry = fssai_expiry_date.strftime('%Y-%m-%d')

        st_obj = {
            'id': store_id,
            'firm_id': firm_id,
            'store_name': store_name,
            'shop_code': shop_code,
            'business_type': "Retail Pharmacy" if i % 4 != 0 else "Wholesale Chemist",
            'drug_license_category': "20B / 21B",
            'owner_name': owner_name,
            'owner_mobile': owner_mobile,
            'owner_whatsapp': owner_mobile,
            'owner_email': owner_email,
            'owner_pan': f"ABCDE{1000 + i}F",
            'owner_aadhaar': f"4321 {1000 + i} {2000 + i}",
            'owner_address': f"Plot {i*4}, Boisar West, Palghar",
            'owner_photo': "",
            'store_logo': "",
            'store_photo': "",
            'contact_phone': owner_mobile,
            'contact_email': owner_email,
            'address_line1': f"Shop No. {i}, Ostwal Empire",
            'address_line2': AREAS_BOISAR[(i - 1) % len(AREAS_BOISAR)],
            'area': "Boisar",
            'city': "Palghar",
            'state': "Maharashtra",
            'pincode': "401501",
            'google_map_url': "https://maps.google.com/?q=19.8000,72.7500",
            'gps_coordinates': "19.8000, 72.7500",
            'dl_20b_number': dl_20b,
            'dl_21b_number': dl_21b,
            'dl_issue_date': dl_issue,
            'dl_expiry_date': dl_expiry,
            'dl_issuing_authority': "FDA Maharashtra (Thane Circle)",
            'dl_renewal_date': dl_expiry,
            'fssai_number': fssai_num,
            'fssai_issue_date': fssai_issue,
            'fssai_expiry_date': fssai_expiry,
            'status': "Active",
            'compliance_score': 95 if offset > 60 else (75 if offset > 0 else 40),
            'compliance_status': "Excellent" if offset > 60 else ("Good" if offset > 0 else "Critical"),
            'created_at': now_str,
            'updated_at': now_str
        }
        stores_list.append(st_obj)

        # Exactly 1 Pharmacist per Medical Store (20 Pharmacists Total)
        ph_id = f"PH-{i:02d}"
        ph_name = f"{FIRST_NAMES[(i*3) % len(FIRST_NAMES)]} {LAST_NAMES[(i*4) % len(LAST_NAMES)]}"
        mspc_num = f"MSPC-{100000 + i*1234 % 899999}"
        ppp_num = f"PPP-MH-{100000 + i*5678 % 899999}"
        
        ppp_exp_days = offset + 5
        ppp_expiry = (today + timedelta(days=ppp_exp_days)).strftime('%Y-%m-%d')
        
        ph_obj = {
            'id': ph_id,
            'store_id': store_id,
            'full_name': ph_name,
            'photo': "",
            'mspc_number': mspc_num,
            'ppp_number': ppp_num,
            'ppp_expiry': ppp_expiry,
            'reg_expiry': ppp_expiry,
            'qualification': QUALIFICATIONS[i % len(QUALIFICATIONS)],
            'joining_date': (now - timedelta(days=300 + i*20)).strftime('%Y-%m-%d'),
            'leaving_date': None,
            'mobile': "8766759824",
            'email': "bhosalevinayakwe@gmail.com",
            'status': "Active",
            'ppp_card_url': f"/static/docs/{firm_id}_PPP_Card.pdf",
            'degree_cert_url': f"/static/docs/{firm_id}_Degree_Certificate.pdf",
            'reg_cert_url': f"/static/docs/{firm_id}_Registration_Certificate.pdf",
            'created_at': now_str,
            'updated_at': now_str
        }
        pharmacists_list.append(ph_obj)

        # 11 Documents per Medical Store (220 total test documents)
        store_docs = [
            ("Drug License", True, dl_issue, dl_expiry, f"DL-{dl_20b}"),
            ("Food License", True, fssai_issue, fssai_expiry, fssai_num),
            ("Rent Agreement", False, None, None, f"LEASE-{1000+i}"),
            ("Light Bill", False, None, None, f"MSEDCL-{4000+i}"),
            ("Namuna 8", False, None, None, f"NAMUNA8-{5000+i}"),
            ("GST Certificate", True, "2020-01-01", dl_expiry, f"27AAAAA{1000+i}A1Z5"),
            ("Shop Act License", True, "2021-04-01", dl_expiry, f"SHOP-ACT-{7000+i}"),
            ("Registration Certificate", True, "2020-05-15", ppp_expiry, mspc_num),
            ("Owner Aadhaar", False, None, None, f"4321 {1000 + i} {2000 + i}"),
            ("Owner PAN", False, None, None, f"ABCDE{1000 + i}F"),
            ("Pharmacist PPP Card", True, "2021-01-01", ppp_expiry, ppp_num)
        ]

        for d_idx, (cat, is_exp, issue_dt, exp_dt, d_num) in enumerate(store_docs):
            doc_id = f"DOC-{i:02d}-{d_idx+1:02d}"
            documents_list.append({
                'id': doc_id,
                'store_id': store_id,
                'firm_id': firm_id,
                'category': cat,
                'title': f"{cat} - {store_name}",
                'document_number': d_num,
                'file_name': f"{cat.lower().replace(' ', '_')}_{store_id}.pdf",
                'file_url': f"/static/docs/{cat.lower().replace(' ', '_')}_{store_id}.pdf",
                'storage_path': f"{firm_id}/{cat}/{cat.lower().replace(' ', '_')}_{store_id}.pdf",
                'file_size_kb': 250 + d_idx * 15,
                'version': 1,
                'is_latest': True,
                'is_expiry_doc': is_exp,
                'reminder_enabled': is_exp,
                'renewal_required': is_exp,
                'issue_date': issue_dt,
                'expiry_date': exp_dt,
                'quality_status': "Passed",
                'quality_notes': "High DPI verification clear",
                'uploaded_by': "Administrator",
                'created_at': now_str,
                'updated_at': now_str
            })

        # Notifications & Queue history generator
        if offset <= 90:
            stage_name = f"{offset} Day" if offset > 0 else "Expired"
            notif_queue_list.append({
                'id': f"Q-DL-{i:02d}",
                'store_id': store_id,
                'recipient_name': owner_name,
                'recipient_email': owner_email,
                'document_type': 'Drug License',
                'document_number': dl_20b,
                'days_remaining': offset,
                'email_subject': f"BCWA Reminder – Drug License expires in {offset} days",
                'email_body_html': f"<p>Reminder notice for {store_name}</p>",
                'status': "Pending" if offset > 0 else "Sent",
                'retry_count': 0,
                'created_at': now_str
            })
            notif_logs_list.append({
                'id': f"LOG-DL-{i:02d}",
                'store_id': store_id,
                'recipient_name': owner_name,
                'recipient_email': owner_email,
                'document_type': 'Drug License',
                'document_number': dl_20b,
                'days_remaining': offset,
                'email_subject': f"BCWA Notice – Drug License {stage_name}",
                'delivery_status': "Success" if i % 5 != 0 else "Failed",
                'sent_at': now_str,
                'created_at': now_str
            })

    # Clear old data and insert 20 Stores, 20 Pharmacists, 220 Documents
    db_table('medical_stores').insert(stores_list).execute()
    db_table('pharmacists').insert(pharmacists_list).execute()
    db_table('documents').insert(documents_list).execute()
    if notif_queue_list:
        db_table('notification_queue').insert(notif_queue_list).execute()
    if notif_logs_list:
        db_table('notification_logs').insert(notif_logs_list).execute()

    activity_logs.append({
        'id': f"ACT-{random.randint(10000, 99999)}",
        'user_name': "System",
        'action': "Database Seed Complete",
        'details': f"Seeded {len(stores_list)} stores, {len(pharmacists_list)} pharmacists, {len(documents_list)} documents.",
        'store_id': None,
        'created_at': now_str
    })
    db_table('activity_logs').insert(activity_logs).execute()

    print("Generating exact 20 Medical Stores synthetic dataset for BCWA Portal...")
    print(f"Seed generation complete: Exactly {len(stores_list)} Medical Stores, {len(pharmacists_list)} Pharmacists, {len(documents_list)} Documents created successfully.")

    # Seed 20 Store Accounts (BCWA-MED-000001 to BCWA-MED-000020) & Passwords (BCWA@1001 to BCWA@1020)
    try:
        from database import create_or_update_store_account
        from sample_pdf_generator import ensure_sample_pdfs_for_store

        for i in range(1, 21):
            firm_id = f"BCWA-MED-{i:06d}"
            store_id = f"BCWA-MED-{i:06d}"
            password = f"BCWA@{1000 + i}"
            store_name = stores_list[i-1]['store_name']
            owner_name = stores_list[i-1]['owner_name']

            create_or_update_store_account(
                firm_id=firm_id,
                password=password,
                store_id=store_id,
                owner_name=owner_name,
                store_name=store_name,
                email="bhosalevinayakwe@gmail.com",
                mobile="8766759824",
                status="Active"
            )
            ensure_sample_pdfs_for_store(store_id, store_name)
        print("Demo Store Accounts (BCWA-MED-000001 to BCWA-MED-000020 with BCWA@1001..1020) seeded successfully.")
    except Exception as e:
        print(f"[STORE ACCOUNTS SEED NOTICE] {e}")

if __name__ == '__main__':
    generate_seed_data()
