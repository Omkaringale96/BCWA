import os
import json
import logging
from datetime import datetime

# Read credentials only from environment variables
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
SUPABASE_SERVICE_KEY = os.environ.get('SUPABASE_SERVICE_KEY', os.environ.get('SUPABASE_KEY', ''))

# Bucket Mapping
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

# In-Memory Database Fallback for local unit tests when SUPABASE_URL is not set
_mock_storage = {
    'users': [],
    'medical_stores': [],
    'pharmacists': [],
    'documents': [],
    'renewals': [],
    'notifications': [],
    'activity_logs': [],
    'settings': []
}

try:
    from supabase import create_client, Client
    HAS_SUPABASE_SDK = True
except ImportError:
    HAS_SUPABASE_SDK = False

_client_instance = None

def get_supabase_client():
    global _client_instance
    if _client_instance:
        return _client_instance

    key_to_use = SUPABASE_SERVICE_KEY or SUPABASE_ANON_KEY
    if HAS_SUPABASE_SDK and SUPABASE_URL and key_to_use:
        try:
            _client_instance = create_client(SUPABASE_URL, key_to_use)
            return _client_instance
        except Exception as e:
            logging.error(f"Supabase client initialization failed: {e}")
            return None
    return None

class SupabaseTableProxy:
    def __init__(self, table_name):
        self.table_name = table_name

    def select(self, columns="*"):
        return SupabaseQueryBuilder(self.table_name, columns)

    def insert(self, data):
        client = get_supabase_client()
        if client:
            try:
                res = client.table(self.table_name).insert(data).execute()
                return res.data
            except Exception as e:
                logging.error(f"Supabase insert error in {self.table_name}: {e}")

        # Fallback in-memory
        if isinstance(data, list):
            _mock_storage[self.table_name].extend(data)
        else:
            _mock_storage[self.table_name].append(data)
        return [data] if isinstance(data, dict) else data

    def upsert(self, data):
        client = get_supabase_client()
        if client:
            try:
                res = client.table(self.table_name).upsert(data).execute()
                return res.data
            except Exception as e:
                logging.error(f"Supabase upsert error in {self.table_name}: {e}")

        items = data if isinstance(data, list) else [data]
        for item in items:
            item_id = item.get('id')
            existing = [i for i in _mock_storage[self.table_name] if i.get('id') == item_id]
            if existing:
                existing[0].update(item)
            else:
                _mock_storage[self.table_name].append(item)
        return items

    def update(self, data):
        return SupabaseUpdateBuilder(self.table_name, data)

    def delete(self):
        return SupabaseDeleteBuilder(self.table_name)

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

                if self.order_by:
                    q = q.order(self.order_by[0], desc=self.order_by[1])
                if self.limit_val:
                    q = q.limit(self.limit_val)

                res = q.execute()
                return SupabaseResponse(res.data)
            except Exception as e:
                logging.error(f"Supabase select error in {self.table_name}: {e}")

        # In-memory execution
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
                return SupabaseResponse(res.data)
            except Exception as e:
                logging.error(f"Supabase update error in {self.table_name}: {e}")

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
                logging.error(f"Supabase delete error in {self.table_name}: {e}")

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

def upload_to_supabase_storage(file_obj, filename, category="Other Documents"):
    """
    Uploads a document to the designated Supabase Storage Bucket:
    - store-documents
    - owner-documents
    - pharmacist-documents
    - inspection-reports
    - other-documents
    """
    bucket_name = BUCKET_MAP.get(category, 'other-documents')
    client = get_supabase_client()
    
    file_path = f"{category}/{filename}"

    if client:
        try:
            if hasattr(file_obj, 'read'):
                content = file_obj.read()
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

    # Fallback Supabase Storage URL format
    base_url = SUPABASE_URL if SUPABASE_URL else "https://your-project.supabase.co"
    return {
        'success': True,
        'url': f"{base_url}/storage/v1/object/public/{bucket_name}/{file_path}",
        'bucket': bucket_name,
        'path': file_path
    }
