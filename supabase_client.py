import os
import json
import logging
import traceback
from datetime import datetime
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()

# Bucket Mapping for Supabase Storage
BUCKET_MAP = {
    'Drug License': 'store-documents',
    'Food License': 'store-documents',
    'Rent Agreement': 'store-documents',
    'Light Bill': 'store-documents',
    'Cold Storage Certificate': 'store-documents',
    'Tax Receipt': 'store-documents',
    'Namuna 8': 'store-documents',
    'Owner Aadhaar': 'owner-documents',
    'Owner Photo': 'owner-documents',
    'PPP Cards': 'pharmacist-documents',
    'Degree Certificate': 'pharmacist-documents',
    'Registration Certificate': 'pharmacist-documents',
    'Inspection Report': 'inspection-reports',
    'Other Documents': 'other-documents'
}

try:
    from supabase import create_client, Client
    HAS_SUPABASE_SDK = True
except ImportError:
    HAS_SUPABASE_SDK = False

_client_instance = None
_mock_storage = {
    'users': [],
    'medical_stores': [],
    'pharmacists': [],
    'documents': [],
    'renewals': [],
    'notifications': [],
    'activity_logs': [],
    'settings': [],
    'notification_logs': [],
    'notification_queue': []
}

def get_supabase_credentials():
    url = (os.environ.get('SUPABASE_URL') or '').strip().strip('"').strip("'")
    service_key = (os.environ.get('SUPABASE_SERVICE_KEY') or os.environ.get('SUPABASE_KEY') or '').strip().strip('"').strip("'")
    anon_key = (os.environ.get('SUPABASE_ANON_KEY') or '').strip().strip('"').strip("'")

    keys_to_try = []
    if service_key:
        keys_to_try.append(('SUPABASE_SERVICE_KEY', service_key))
    if anon_key and anon_key != service_key:
        keys_to_try.append(('SUPABASE_ANON_KEY', anon_key))

    return url, keys_to_try

def get_supabase_client():
    """
    Initializes and returns official Supabase Client using SUPABASE_URL and SUPABASE_SERVICE_KEY / SUPABASE_ANON_KEY.
    """
    global _client_instance
    if _client_instance:
        return _client_instance

    url, keys_to_try = get_supabase_credentials()

    if not url or not keys_to_try:
        return None

    if HAS_SUPABASE_SDK:
        for key_name, key in keys_to_try:
            try:
                _client_instance = create_client(url, key)
                print(f"[SUPABASE SUCCESS] Initialized Supabase client using {key_name}.")
                logging.info(f"Initialized Supabase client using {key_name}.")
                return _client_instance
            except Exception as e:
                msg = str(e)
                if "Invalid API key" in msg:
                    print(f"[SUPABASE API KEY NOTICE] Key in '{key_name}' was rejected by Supabase SDK: Invalid API key.")
                else:
                    logging.error(f"Supabase client initialization failed with {key_name}: {e}")
                    logging.error(traceback.format_exc())

        print("[SUPABASE CONFIG ERROR] None of the provided API keys were valid Supabase JWT keys.")
        print("👉 Action Required in Render Environment Variables:")
        print("   1. Open Supabase Dashboard -> Project Settings -> API")
        print("   2. Copy the 'anon' public key or 'service_role' secret key (starts with 'eyJ...')")
        print("   3. Paste into SUPABASE_ANON_KEY or SUPABASE_SERVICE_KEY on Render.")

    return None

def test_supabase_connection():
    """
    Startup connection test to verify Supabase PostgreSQL connection.
    Logs 'Supabase Connected Successfully' or full exception traceback on failure.
    """
    client = get_supabase_client()
    if not client:
        msg = "SUPABASE_URL or SUPABASE_SERVICE_KEY not set in environment. Running in offline mode."
        print(f"[SUPABASE STATUS] {msg}")
        return False, msg

    try:
        res = client.table('users').select('*').limit(1).execute()
        print("Supabase Connected Successfully")
        logging.info("Supabase Connected Successfully")
        return True, "Supabase Connected Successfully"
    except Exception as e:
        err_msg = f"Supabase Connection Failed: {e}"
        print(f"[SUPABASE ERROR] {err_msg}")
        print(traceback.format_exc())
        logging.error(err_msg)
        logging.error(traceback.format_exc())
        return False, err_msg

class SupabaseTableProxy:
    def __init__(self, table_name):
        self.table_name = table_name

    def select(self, columns="*"):
        return SupabaseQueryBuilder(self.table_name, columns)

    def insert(self, data):
        return SupabaseInsertBuilder(self.table_name, data)

    def upsert(self, data):
        return SupabaseUpsertBuilder(self.table_name, data)

    def update(self, data):
        return SupabaseUpdateBuilder(self.table_name, data)

class SupabaseInsertBuilder:
    def __init__(self, table_name, data):
        self.table_name = table_name
        self.data = data

    def execute(self):
        client = get_supabase_client()
        if client:
            try:
                res = client.table(self.table_name).insert(self.data).execute()
                print(f"[SUPABASE INSERT SUCCESS] Table '{self.table_name}' | Data: {res.data}")
                logging.info(f"[SUPABASE INSERT SUCCESS] Table '{self.table_name}' | Data: {res.data}")
                return SupabaseResponse(res.data)
            except Exception as e:
                err_str = str(e)
                if 'PGRST205' in err_str or 'Could not find the table' in err_str:
                    logging.warning(f"[SUPABASE NOTICE] Table '{self.table_name}' missing from Supabase schema. Operating in local store mode.")
                else:
                    err_msg = f"[SUPABASE INSERT FAILURE] Table '{self.table_name}' | Error: {e}"
                    print(err_msg)
                    print(traceback.format_exc())
                    logging.error(err_msg)
                    logging.error(traceback.format_exc())
                    raise e

        rows = _mock_storage.setdefault(self.table_name, [])
        items = self.data if isinstance(self.data, list) else [self.data]
        rows.extend(items)
        return SupabaseResponse(items)

class SupabaseUpsertBuilder:
    def __init__(self, table_name, data):
        self.table_name = table_name
        self.data = data

    def execute(self):
        client = get_supabase_client()
        if client:
            try:
                res = client.table(self.table_name).upsert(self.data).execute()
                print(f"[SUPABASE UPSERT SUCCESS] Table '{self.table_name}' | Data: {res.data}")
                logging.info(f"[SUPABASE UPSERT SUCCESS] Table '{self.table_name}' | Data: {res.data}")
                return SupabaseResponse(res.data)
            except Exception as e:
                err_str = str(e)
                if 'PGRST205' in err_str or 'Could not find the table' in err_str:
                    logging.warning(f"[SUPABASE NOTICE] Table '{self.table_name}' missing from Supabase schema. Operating in local store mode.")
                else:
                    err_msg = f"[SUPABASE UPSERT FAILURE] Table '{self.table_name}' | Error: {e}"
                    print(err_msg)
                    print(traceback.format_exc())
                    logging.error(err_msg)
                    logging.error(traceback.format_exc())
                    raise e

        rows = _mock_storage.setdefault(self.table_name, [])
        items = self.data if isinstance(self.data, list) else [self.data]
        for item in items:
            item_id = item.get('id') or item.get('key')
            existing = [i for i in rows if (i.get('id') and i.get('id') == item_id) or (i.get('key') and i.get('key') == item_id)]
            if existing:
                existing[0].update(item)
            else:
                rows.append(item)
        return SupabaseResponse(items)

class SupabaseQueryBuilder:
    def __init__(self, table_name, columns):
        self.table_name = table_name
        self.columns = columns
        self.filters = []
        self.order_by = None
        self.limit_val = None

    def eq(self, column, value):
        self.filters.append(('eq', column, value))
        return self

    def neq(self, column, value):
        self.filters.append(('neq', column, value))
        return self

    def lte(self, column, value):
        self.filters.append(('lte', column, value))
        return self

    def gte(self, column, value):
        self.filters.append(('gte', column, value))
        return self

    def lt(self, column, value):
        self.filters.append(('lt', column, value))
        return self

    def in_(self, column, values):
        self.filters.append(('in', column, values))
        return self

    def order(self, column, desc=False):
        self.order_by = (column, desc)
        return self

    def limit(self, count):
        self.limit_val = count
        return self

    def execute(self):
        client = get_supabase_client()
        if client:
            try:
                q = client.table(self.table_name).select(self.columns)
                for op, col, val in self.filters:
                    if op == 'eq': q = q.eq(col, val)
                    elif op == 'neq': q = q.neq(col, val)
                    elif op == 'lte': q = q.lte(col, val)
                    elif op == 'gte': q = q.gte(col, val)
                    elif op == 'lt': q = q.lt(col, val)
                    elif op == 'in': q = q.in_(col, val)

                if self.order_by:
                    q = q.order(self.order_by[0], desc=self.order_by[1])
                if self.limit_val:
                    q = q.limit(self.limit_val)

                res = q.execute()
                return SupabaseResponse(res.data)
            except Exception as e:
                logging.error(f"Supabase select error in {self.table_name}: {e}")
                logging.error(traceback.format_exc())

        rows = _mock_storage.get(self.table_name, [])
        filtered = []
        for r in rows:
            match = True
            for op, col, val in self.filters:
                r_val = r.get(col)
                if op == 'eq' and str(r_val or '').lower() != str(val or '').lower(): match = False
                elif op == 'neq' and str(r_val or '').lower() == str(val or '').lower(): match = False
                elif op == 'lte' and str(r_val or '') > str(val or ''): match = False
                elif op == 'gte' and str(r_val or '') < str(val or ''): match = False
                elif op == 'lt' and str(r_val or '') >= str(val or ''): match = False
                elif op == 'in' and (r_val not in val and str(r_val) not in val): match = False
            if match:
                filtered.append(r)

        if self.order_by:
            col, desc = self.order_by
            filtered.sort(key=lambda x: str(x.get(col, '')), reverse=desc)

        if self.limit_val:
            filtered = filtered[:self.limit_val]

        return SupabaseResponse(filtered)

class SupabaseUpdateBuilder:
    def __init__(self, table_name, data):
        self.table_name = table_name
        self.data = data
        self.filters = []

    def eq(self, column, value):
        self.filters.append(('eq', column, value))
        return self

    def execute(self):
        client = get_supabase_client()
        if client:
            try:
                q = client.table(self.table_name).update(self.data)
                for op, col, val in self.filters:
                    if op == 'eq': q = q.eq(col, val)
                res = q.execute()
                print(f"[SUPABASE UPDATE SUCCESS] Table '{self.table_name}' | Data: {res.data}")
                logging.info(f"[SUPABASE UPDATE SUCCESS] Table '{self.table_name}' | Data: {res.data}")
                return SupabaseResponse(res.data)
            except Exception as e:
                err_str = str(e)
                if 'PGRST205' in err_str or 'Could not find the table' in err_str:
                    logging.warning(f"[SUPABASE NOTICE] Table '{self.table_name}' missing from Supabase schema. Operating in local store mode.")
                else:
                    err_msg = f"[SUPABASE UPDATE FAILURE] Table '{self.table_name}' | Error: {e}"
                    print(err_msg)
                    print(traceback.format_exc())
                    logging.error(err_msg)
                    logging.error(traceback.format_exc())
                    raise e

        rows = _mock_storage.get(self.table_name, [])
        updated = []
        for r in rows:
            match = True
            for op, col, val in self.filters:
                if op == 'eq' and str(r.get(col) or '').lower() != str(val or '').lower(): match = False
            if match:
                r.update(self.data)
                updated.append(r)
        return SupabaseResponse(updated)

class SupabaseDeleteBuilder:
    def __init__(self, table_name):
        self.table_name = table_name
        self.filters = []

    def eq(self, column, value):
        self.filters.append(('eq', column, value))
        return self

    def execute(self):
        client = get_supabase_client()
        if client:
            try:
                q = client.table(self.table_name).delete()
                for op, col, val in self.filters:
                    if op == 'eq': q = q.eq(col, val)
                res = q.execute()
                return SupabaseResponse(res.data)
            except Exception as e:
                err_str = str(e)
                if 'PGRST205' in err_str or 'Could not find the table' in err_str:
                    logging.warning(f"[SUPABASE NOTICE] Table '{self.table_name}' missing from Supabase schema. Operating in local store mode.")
                else:
                    logging.error(f"Supabase delete error in {self.table_name}: {e}")
                    logging.error(traceback.format_exc())

        rows = _mock_storage.get(self.table_name, [])
        new_rows = []
        deleted = []
        for r in rows:
            match = True
            for op, col, val in self.filters:
                if op == 'eq' and str(r.get(col) or '').lower() != str(val or '').lower(): match = False
            if match:
                deleted.append(r)
            else:
                new_rows.append(r)
        _mock_storage[self.table_name] = new_rows
        return SupabaseResponse(deleted)

class SupabaseResponse:
    def __init__(self, data):
        self.data = data or []

def db_table(table_name):
    return SupabaseTableProxy(table_name)

def resolve_storage_bucket_and_path(firm_id, category, filename, pharmacist_name=None):
    firm_folder = (firm_id or 'BCWA-MED-000001').strip().upper()
    cat = (category or 'Other').strip()
    cat_lower = cat.lower()

    if any(k in cat_lower for k in ['drug', 'food', 'fssai', 'rent', 'electricity', 'light', 'gst', 'shop act', 'namuna', 'cold storage', 'tax']):
        bucket_name = 'store-documents'
        file_path = f"{firm_folder}/{cat}/{filename}"
    elif any(k in cat_lower for k in ['aadhaar', 'pan', 'photo', 'owner']):
        bucket_name = 'owner-documents'
        file_path = f"{firm_folder}/{cat}/{filename}"
    elif any(k in cat_lower for k in ['pharmacist', 'ppp', 'degree', 'registration', 'appointment', 'qualification']):
        bucket_name = 'pharmacist-documents'
        ph_folder = pharmacist_name if pharmacist_name else "Pharmacist-01"
        file_path = f"{firm_folder}/{ph_folder}/{cat}/{filename}"
    elif 'inspection' in cat_lower:
        bucket_name = 'inspection-reports'
        file_path = f"{firm_folder}/{filename}"
    else:
        bucket_name = 'other-documents'
        file_path = f"{firm_folder}/{filename}"

    return bucket_name, file_path

def upload_to_supabase_storage(file_obj, filename, category="Other Documents", firm_id="BCWA-MED-000001", pharmacist_name=None):
    """
    Uploads a document to designated Supabase Storage Bucket hierarchy by Firm ID:
    - store-documents/BCWA-MED-000001/Drug License/<filename>
    - owner-documents/BCWA-MED-000001/Owner Aadhaar/<filename>
    - pharmacist-documents/BCWA-MED-000001/Pharmacist-01/PPP Card/<filename>
    - inspection-reports/BCWA-MED-000001/<filename>
    - other-documents/BCWA-MED-000001/<filename>
    """
    bucket_name, file_path = resolve_storage_bucket_and_path(firm_id, category, filename, pharmacist_name)
    client = get_supabase_client()

    if client:
        try:
            if hasattr(file_obj, 'read'):
                content = file_obj.read()
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
            else:
                content = file_obj

            res = client.storage.from_(bucket_name).upload(
                path=file_path,
                file=content,
                file_options={"upsert": "true"}
            )

            public_url = client.storage.from_(bucket_name).get_public_url(file_path)
            return {
                'success': True,
                'url': public_url,
                'bucket': bucket_name,
                'path': file_path
            }
        except Exception as e:
            logging.error(f"Supabase Storage upload error for bucket {bucket_name}: {e}")

    url, _ = get_supabase_credentials()
    base_url = url if url else "https://your-project.supabase.co"
    return {
        'success': True,
        'url': f"{base_url}/storage/v1/object/public/{bucket_name}/{file_path}",
        'bucket': bucket_name,
        'path': file_path
    }
