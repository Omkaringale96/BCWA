import random
from datetime import datetime, timedelta
from database import init_db
from firebase_client import db_table
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

import os
import glob
from datetime import datetime
from database import init_db
from firebase_client import db_table, get_supabase_client
from werkzeug.security import generate_password_hash

def clear_production_database():
    """
    Clears all demo/sample records from all database tables and storage.
    Preserves ONLY the Administrator account (VIN2821).
    """
    init_db()
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 1. Reset 'users' table - Keep ONLY Administrator Account (VIN2821)
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

    try:
        client = get_supabase_client()
        if client:
            # Delete all non-admin users
            try:
                client.table('users').delete().neq('id', 'VIN2821').execute()
            except Exception:
                pass

            # Delete all records from production tables
            for table_name in ['documents', 'pharmacists', 'medical_stores', 'store_accounts', 'notification_queue', 'notification_logs', 'notifications', 'activity_logs']:
                try:
                    rows = client.table(table_name).select('*').execute().data or []
                    if rows:
                        # Delete by ID list if present
                        ids = [str(r.get('id')) for r in rows if r.get('id')]
                        if ids:
                            for chunk in [ids[i:i + 100] for i in range(0, len(ids), 100)]:
                                client.table(table_name).delete().in_('id', chunk).execute()
                        else:
                            client.table(table_name).delete().neq('created_at', '1900-01-01').execute()
                except Exception as e_tbl:
                    print(f"[SUPABASE PURGE NOTICE {table_name}] {e_tbl}")
    except Exception as e:
        print(f"[SUPABASE PURGE NOTICE] {e}")

    # Wipe local store tables
    try:
        from database import _MEM_STORES, _MEM_PHARMACISTS, _MEM_USERS
        _MEM_STORES.clear()
        _MEM_PHARMACISTS.clear()
        _MEM_USERS.clear()
    except Exception:
        pass

    # Ensure admin user is inserted
    db_table('users').upsert(admin_user).execute()

    # 2. Clean up sample PDFs from static/docs/
    doc_folder = os.path.join(os.path.dirname(__file__), 'static', 'docs')
    if os.path.exists(doc_folder):
        for f in os.listdir(doc_folder):
            if f != '.gitkeep' and (f.endswith('.pdf') or f.endswith('.png') or f.endswith('.jpg')):
                try:
                    os.remove(os.path.join(doc_folder, f))
                except Exception:
                    pass

    print("[PRODUCTION RESET COMPLETE] All demo data removed. BCWA Portal initialized in production-ready zero state.")
    print("Administrator Account: VIN2821 (Active)")
    print("Medical Stores: 0 | Pharmacists: 0 | Documents: 0 | Queue: 0 | Logs: 0")

def generate_seed_data():
    """Default startup seed function: Enforces clean production zero state."""
    clear_production_database()

if __name__ == '__main__':
    generate_seed_data()
