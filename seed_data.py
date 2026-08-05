import sqlite3
import random
from datetime import datetime, timedelta
import os
import json
from database import init_db, DB_FILE

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
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM medical_stores")
    cursor.execute("DELETE FROM pharmacists")
    cursor.execute("DELETE FROM documents")
    cursor.execute("DELETE FROM notifications")
    cursor.execute("DELETE FROM reminders")
    cursor.execute("DELETE FROM activity_logs")
    cursor.execute("DELETE FROM users")

    print("Generating exact 20 Medical Stores synthetic dataset for BCWA Portal...")
    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')

    users = [
        ("USR-1001", "BCWA Admin", "admin@bcwaportal.in", "BCWA@2026", "Administrator", "Active", now_str),
        ("USR-1002", "Office Staff", "staff@bcwaportal.in", "BCWA@2026", "Office Staff", "Active", now_str),
        ("USR-1003", "Inspector ReadOnly", "auditor@bcwaportal.in", "BCWA@2026", "Read Only", "Active", now_str)
    ]
    cursor.executemany("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)", users)

    stores_list = []
    pharmacists_list = []
    documents_list = []
    notifications_list = []
    activity_logs_list = []
    reminders_list = []

    for i in range(1, 21):
        store_id = f"MS-{1000 + i}"
        shop_code = f"BCWA-BSR-{1000 + i}"
        prefix = STORE_PREFIXES[i - 1] if i <= len(STORE_PREFIXES) else random.choice(STORE_PREFIXES)
        suffix = random.choice(STORE_SUFFIXES)
        store_name = f"{prefix} {suffix}"

        owner_fn = random.choice(FIRST_NAMES)
        owner_ln = random.choice(LAST_NAMES)
        owner_name = f"{owner_fn} {owner_ln}"
        mobile_num = f"+91 {random.choice([98, 97, 96, 99, 93, 88])}{random.randint(1000000, 9999999)}"

        area = random.choice(AREAS_BOISAR)
        addr1 = f"Shop No. {i}, Ground Floor, {random.choice(['Sai Plaza', 'Gharat Complex', 'Ostwal Shopping Center', 'Commercial Complex', 'Station Heights', 'Vighnaharta Arcade'])}"

        days_offset_dl = random.choice([
            random.randint(-180, -5),
            random.randint(5, 30),
            random.randint(31, 90),
            random.randint(100, 1200)
        ])
        dl_exp = (now + timedelta(days=days_offset_dl)).strftime('%Y-%m-%d')
        dl_issue = (now + timedelta(days=days_offset_dl - 1825)).strftime('%Y-%m-%d')

        days_offset_fssai = random.choice([
            random.randint(-120, -10),
            random.randint(10, 45),
            random.randint(46, 90),
            random.randint(120, 1095)
        ])
        fssai_exp = (now + timedelta(days=days_offset_fssai)).strftime('%Y-%m-%d')
        fssai_issue = (now + timedelta(days=days_offset_fssai - 1095)).strftime('%Y-%m-%d')

        dl_20b = f"MH-TZ4-{random.randint(100000, 999999)}"
        dl_21b = f"MH-TZ4-{random.randint(100000, 999999)}"
        fssai_no = f"21524{random.randint(100000000, 999999999)}"

        score = 85
        if days_offset_dl < 0 or days_offset_fssai < 0:
            score -= 35
        elif days_offset_dl <= 90 or days_offset_fssai <= 90:
            score -= 15

        status_str = 'Excellent' if score >= 90 else ('Good' if score >= 75 else ('Needs Attention' if score >= 50 else 'Critical'))

        stores_list.append((
            store_id, store_name, shop_code, 'Retail Pharmacy', '20B / 21B',
            owner_name, mobile_num, mobile_num, f"{owner_fn.lower()}.{owner_ln.lower()}@gmail.com",
            f"ABCDE{random.randint(1000,9999)}F", f"{random.randint(2000,9999)} {random.randint(1000,9999)} {random.randint(1000,9999)}",
            f"Flat {random.randint(101,404)}, {area}, Boisar", "",
            "", "", mobile_num, f"contact@{store_name.lower().replace(' ', '').replace('&', '')}.com",
            addr1, area, area, "Palghar", "Maharashtra", "401501",
            f"https://maps.google.com/?q=19.{random.randint(7900,8100)},72.{random.randint(7400,7600)}",
            f"19.{random.randint(7900,8100)}, 72.{random.randint(7400,7600)}",
            dl_20b, dl_21b, dl_issue, dl_exp, "FDA Maharashtra (Thane Circle)",
            (now + timedelta(days=days_offset_dl - 30)).strftime('%Y-%m-%d'),
            f"/static/docs/dl_{store_id.lower()}.pdf",
            fssai_no, fssai_issue, fssai_exp, f"/static/docs/fssai_{store_id.lower()}.pdf",
            score, status_str, 'Active', now_str, now_str
        ))

    ph_count = 1
    for store in stores_list:
        s_id = store[0]
        s_name = store[1]
        num_ph = random.randint(2, 3)

        for j in range(num_ph):
            ph_id = f"PH-{2000 + ph_count}"
            p_fn = random.choice(FIRST_NAMES)
            p_ln = random.choice(LAST_NAMES)
            full_name = f"{p_fn} {p_ln}"
            mspc_no = f"MSPC-{random.randint(100000, 999999)}"
            ppp_no = f"PPP-MH-{random.randint(100000, 999999)}"

            ppp_offset = random.choice([
                random.randint(-90, -1),
                random.randint(10, 60),
                random.randint(91, 730)
            ])
            ppp_exp = (now + timedelta(days=ppp_offset)).strftime('%Y-%m-%d')
            reg_exp = (now + timedelta(days=ppp_offset + 365)).strftime('%Y-%m-%d')
            join_date = (now - timedelta(days=random.randint(30, 1500))).strftime('%Y-%m-%d')

            pharmacists_list.append((
                ph_id, s_id, full_name, "", mspc_no, ppp_no, ppp_exp, reg_exp,
                random.choice(QUALIFICATIONS), join_date, "",
                f"+91 {random.choice([98, 97, 96, 91, 88])}{random.randint(1000000, 9999999)}",
                f"{p_fn.lower()}.pharmacist@gmail.com", "Active",
                f"/static/docs/ppp_{ph_id.lower()}.pdf",
                f"/static/docs/degree_{ph_id.lower()}.pdf",
                f"/static/docs/mspc_{ph_id.lower()}.pdf",
                now_str, now_str
            ))
            ph_count += 1

    doc_id_counter = 1
    for store in stores_list:
        s_id = store[0]
        s_name = store[1]

        selected_cats = random.sample(DOC_CATEGORIES, k=random.randint(6, 8))
        for cat in selected_cats:
            doc_id = f"DOC-{5000 + doc_id_counter}"
            title = f"{cat} - {s_name}"
            fname = f"{cat.lower().replace(' ', '_')}_{s_id.lower()}.pdf"
            size_kb = random.randint(150, 1200)

            documents_list.append((
                doc_id, s_id, cat, title, fname, f"/static/docs/{fname}",
                size_kb, 1, (now - timedelta(days=365)).strftime('%Y-%m-%d'),
                (now + timedelta(days=random.randint(30, 730))).strftime('%Y-%m-%d'),
                'Passed', 'Resolution 300 DPI, Text crisp and readable',
                'Office Staff', now_str
            ))
            doc_id_counter += 1

    for i in range(1, 15):
        notifications_list.append((
            f"NOTIF-{100 + i}",
            f"License Expiry Alert #{i}",
            f"Renewal deadline approaching for {random.choice(stores_list)[1]}",
            random.choice(['Warning', 'Danger', 'Info']),
            'MedicalStore', random.choice(stores_list)[0],
            random.choice([0, 1]), now_str
        ))

    for i in range(1, 20):
        st = random.choice(stores_list)
        reminders_list.append((
            f"REM-{200 + i}", st[0], 'Drug License', st[5], st[6],
            random.choice([90, 60, 30, 15, 7, 1]),
            (now - timedelta(days=random.randint(1, 15))).strftime('%Y-%m-%d'),
            'Sent', f"Automated SMS & WhatsApp reminder sent to owner {st[5]} for license {st[25]}"
        ))

    for i in range(1, 25):
        st = random.choice(stores_list)
        activity_logs_list.append((
            f"ACT-{300 + i}",
            random.choice(['BCWA Admin', 'Office Staff']),
            random.choice(['Store Updated', 'Pharmacist Added', 'Document Uploaded', 'Reminder Sent', 'Compliance Checked']),
            f"Processed activity for {st[1]} (Code: {st[2]})",
            st[0], (now - timedelta(hours=random.randint(1, 120))).strftime('%Y-%m-%d %H:%M:%S')
        ))

    cursor.executemany("INSERT INTO medical_stores VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", stores_list)
    cursor.executemany("INSERT INTO pharmacists VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", pharmacists_list)
    cursor.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", documents_list)
    cursor.executemany("INSERT INTO notifications VALUES (?,?,?,?,?,?,?,?)", notifications_list)
    cursor.executemany("INSERT INTO reminders VALUES (?,?,?,?,?,?,?,?,?)", reminders_list)
    cursor.executemany("INSERT INTO activity_logs VALUES (?,?,?,?,?,?)", activity_logs_list)

    conn.commit()
    conn.close()

    print(f"Seed generation complete: Exactly {len(stores_list)} Medical Stores, {len(pharmacists_list)} Pharmacists, {len(documents_list)} Documents created successfully.")

if __name__ == '__main__':
    generate_seed_data()
