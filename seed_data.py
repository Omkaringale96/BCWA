import random
from datetime import datetime, timedelta
from database import init_db
from supabase_client import db_table

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

    # Seed ONLY Administrator Account (Vinayak VIN2821)
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
    db_table('users').insert(admin_user).execute()

    stores_list = []
    pharmacists_list = []
    documents_list = []
    activity_logs = []
    notifications = []

    for i in range(1, 21):
        store_id = f"MS-10{i:02d}"
        shop_code = f"BCWA-BSR-{100 + i}"
        store_name = f"{STORE_PREFIXES[(i-1) % len(STORE_PREFIXES)]} {STORE_SUFFIXES[(i-1) % len(STORE_SUFFIXES)]}"
        owner_name = f"{FIRST_NAMES[(i*2) % len(FIRST_NAMES)]} {LAST_NAMES[(i*3) % len(LAST_NAMES)]}"
        owner_mobile = "8766759824"
        owner_email = "bhosalevinayakwe@gmail.com"
        
        dl_20b = f"MH-TZ4-{random.randint(100000, 999999)}"
        dl_21b = f"MH-TZ4-{random.randint(100000, 999999)}"
        fssai_num = f"21524{random.randint(100000000, 999999999)}"
        
        issue_days_ago = random.randint(300, 1400)
        expiry_days_ahead = random.randint(-40, 730)
        
        dl_issue = (now - timedelta(days=issue_days_ago)).strftime('%Y-%m-%d')
        dl_expiry = (now + timedelta(days=expiry_days_ahead)).strftime('%Y-%m-%d')
        
        fssai_issue = (now - timedelta(days=issue_days_ago - 50)).strftime('%Y-%m-%d')
        fssai_expiry = (now + timedelta(days=expiry_days_ahead + 60)).strftime('%Y-%m-%d')

        st_obj = {
            'id': store_id,
            'store_name': store_name,
            'shop_code': shop_code,
            'business_type': "Retail Pharmacy" if i % 4 != 0 else "Wholesale Chemist",
            'drug_license_category': "20B / 21B",
            'owner_name': owner_name,
            'owner_mobile': owner_mobile,
            'owner_whatsapp': owner_mobile,
            'owner_email': owner_email,
            'owner_pan': f"ABCDE{random.randint(1000,9999)}F",
            'owner_aadhaar': f"4321 {random.randint(1000,9999)} {random.randint(1000,9999)}",
            'owner_address': f"Plot {i*4}, Boisar West, Palghar",
            'owner_photo': "",
            'store_logo': "",
            'store_photo': "",
            'contact_phone': owner_mobile,
            'contact_email': owner_email,
            'address_line1': f"Shop No. {i}, Ostwal Empire",
            'address_line2': AREAS_BOISAR[i % len(AREAS_BOISAR)],
            'area': "Boisar",
            'city': "Palghar",
            'state': "Maharashtra",
            'pincode': "401501",
            'google_map_url': f"https://maps.google.com/?q=19.8000,72.7500",
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
            'compliance_score': 95 if expiry_days_ahead > 60 else (75 if expiry_days_ahead > 0 else 40),
            'compliance_status': "Excellent" if expiry_days_ahead > 60 else ("Good" if expiry_days_ahead > 0 else "Critical"),
            'created_at': now_str,
            'updated_at': now_str
        }
        stores_list.append(st_obj)

        num_pharmacists = random.randint(2, 3)
        for p_idx in range(num_pharmacists):
            ph_id = f"PH-{i:02d}{p_idx+1}"
            ph_name = f"{FIRST_NAMES[(i+p_idx*3) % len(FIRST_NAMES)]} {LAST_NAMES[(i+p_idx*5) % len(LAST_NAMES)]}"
            mspc_num = f"MSPC-{random.randint(100000, 999999)}"
            ppp_num = f"PPP-MH-{random.randint(100000, 999999)}"
            
            ppp_exp_days = random.randint(-15, 600)
            ppp_expiry = (now + timedelta(days=ppp_exp_days)).strftime('%Y-%m-%d')
            
            ph_obj = {
                'id': ph_id,
                'store_id': store_id,
                'full_name': ph_name,
                'photo': "",
                'mspc_number': mspc_num,
                'ppp_number': ppp_num,
                'ppp_expiry': ppp_expiry,
                'reg_expiry': ppp_expiry,
                'qualification': QUALIFICATIONS[random.randint(0, len(QUALIFICATIONS)-1)],
                'joining_date': (now - timedelta(days=random.randint(100, 800))).strftime('%Y-%m-%d'),
                'leaving_date': None,
                'mobile': "8766759824",
                'email': "bhosalevinayakwe@gmail.com",
                'status': "Active",
                'ppp_card_url': f"/static/docs/ppp_{ph_id}.pdf",
                'degree_cert_url': f"/static/docs/degree_{ph_id}.pdf",
                'reg_cert_url': f"/static/docs/reg_{ph_id}.pdf",
                'created_at': now_str,
                'updated_at': now_str
            }
            pharmacists_list.append(ph_obj)

        for cat in ["Drug License", "Food License", "PPP Cards", "Rent Agreement", "Namuna 8", "Light Bill"]:
            doc_id = f"DOC-{i:02d}-{random.randint(100,999)}"
            documents_list.append({
                'id': doc_id,
                'store_id': store_id,
                'category': cat,
                'title': f"{cat} - {store_name}",
                'file_name': f"{cat.lower().replace(' ', '_')}_{store_id}.pdf",
                'file_url': f"/static/docs/{cat.lower().replace(' ', '_')}_{store_id}.pdf",
                'file_size_kb': random.randint(120, 850),
                'version': 1,
                'issue_date': dl_issue,
                'expiry_date': dl_expiry,
                'quality_status': "Passed",
                'quality_notes': "DPI scan verified readable",
                'uploaded_by': "Office Staff",
                'created_at': now_str,
                'updated_at': now_str
            })

        if expiry_days_ahead <= 90:
            notifications.append({
                'id': f"NOTIF-{i:02d}-DL",
                'store_id': store_id,
                'title': f"Drug License Renewal Warning - {store_name}",
                'message': f"Drug License 20B/21B expires on {dl_expiry}. Please initiate renewal.",
                'type': "Warning" if expiry_days_ahead > 0 else "Danger",
                'target_date': dl_expiry,
                'days_remaining': expiry_days_ahead,
                'is_read': False,
                'created_at': now_str
            })

    db_table('medical_stores').insert(stores_list).execute()
    db_table('pharmacists').insert(pharmacists_list).execute()
    db_table('documents').insert(documents_list).execute()
    if notifications:
        db_table('notifications').insert(notifications).execute()

    activity_logs.append({
        'id': f"ACT-{random.randint(10000, 99999)}",
        'user_name': "System",
        'action': "Database Initialized",
        'details': f"Seeded {len(stores_list)} stores, {len(pharmacists_list)} pharmacists, and {len(documents_list)} documents.",
        'store_id': None,
        'created_at': now_str
    })
    db_table('activity_logs').insert(activity_logs).execute()

    print(f"Generating exact 20 Medical Stores synthetic dataset for BCWA Portal...")
    print(f"Seed generation complete: Exactly {len(stores_list)} Medical Stores, {len(pharmacists_list)} Pharmacists, {len(documents_list)} Documents created successfully.")

    # Ensure ALL existing stores and pharmacists in database are updated with target mobile and email
    try:
        existing_stores = db_table('medical_stores').select('*').execute().data or []
        for s in existing_stores:
            s_id = s.get('id')
            db_table('medical_stores').update({
                'owner_mobile': '8766759824',
                'owner_whatsapp': '8766759824',
                'owner_email': 'bhosalevinayakwe@gmail.com',
                'contact_phone': '8766759824',
                'contact_email': 'bhosalevinayakwe@gmail.com'
            }).eq('id', s_id).execute()

        existing_pharmacists = db_table('pharmacists').select('*').execute().data or []
        for p in existing_pharmacists:
            p_id = p.get('id')
            db_table('pharmacists').update({
                'mobile': '8766759824',
                'email': 'bhosalevinayakwe@gmail.com'
            }).eq('id', p_id).execute()
    except Exception as e:
        print(f"[SEED UPDATE NOTICE] {e}")

    # Seed Demo Store Accounts (MED0001 to MED0005) & Sample PDFs
    try:
        from database import create_or_update_store_account
        from sample_pdf_generator import ensure_sample_pdfs_for_store

        demo_stores = [
            ("MED0001", "MS-1001", "Vinayak Bhosale", "Apex Chemist & Druggists"),
            ("MED0002", "MS-1002", "Rajesh Sharma", "Lifeline Medicare"),
            ("MED0003", "MS-1003", "Amit Patil", "Care & Cure Pharma"),
            ("MED0004", "MS-1004", "Sunil Verma", "Wellness Medicals"),
            ("MED0005", "MS-1005", "Pooja Mehta", "National Pharmacy")
        ]

        for firm_id, store_id, owner_name, store_name in demo_stores:
            create_or_update_store_account(
                firm_id=firm_id,
                password="BCWA@123",
                store_id=store_id,
                owner_name=owner_name,
                store_name=store_name,
                email="bhosalevinayakwe@gmail.com",
                mobile="8766759824",
                status="Active"
            )
            ensure_sample_pdfs_for_store(store_id, store_name)
        print("Demo Store Accounts (MED0001-MED0005) seeded successfully.")
    except Exception as e:
        print(f"[STORE ACCOUNTS SEED NOTICE] {e}")

if __name__ == '__main__':
    generate_seed_data()
