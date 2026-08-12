"""
BCWA Nexus - Firebase Cloud Firestore & Storage Client
Handles initialization, Firestore database operations, and document storage.
"""
import os
import re
import json
import logging
import traceback
from datetime import datetime
import urllib.parse

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
    HAS_FIREBASE_SDK = True
except ImportError:
    HAS_FIREBASE_SDK = False

_firebase_app = None
_firestore_db = None

DEFAULT_STORAGE_BUCKET = "bcwa-233d5.firebasestorage.app"

CATEGORY_FOLDER_MAP = {
    'drug license': 'DrugLicense',
    '20b / 21b': 'DrugLicense',
    '20b': 'DrugLicense',
    '21b': 'DrugLicense',
    'fssai license': 'FoodLicense',
    'food license': 'FoodLicense',
    'fssai': 'FoodLicense',
    'ppp card': 'PPP',
    'ppp certificate': 'PPP',
    'ppp': 'PPP',
    'owner photo': 'Owner',
    'owner': 'Owner',
    'aadhaar': 'Aadhaar',
    'aadhaar card': 'Aadhaar',
    'pan': 'PAN',
    'pan card': 'PAN',
    'rent agreement': 'RentAgreement',
    'shop photos': 'ShopPhotos',
    'store photo': 'ShopPhotos',
    'electricity bill': 'ElectricityBill',
    'cold storage': 'ColdStorage'
}

def get_firebase_credentials_path():
    """Returns path to firebase credentials file if present."""
    custom_path = os.environ.get("FIREBASE_CREDENTIALS_PATH", "firebase_credentials.json")
    if os.path.exists(custom_path):
        return custom_path
    
    # Search for any firebase-adminsdk json file in root directory
    for f in os.listdir("."):
        if f.endswith(".json") and ("firebase-adminsdk" in f or "firebase_credentials" in f):
            return f
    return None

def get_firebase_db():
    """Initializes Firebase Admin SDK and returns Firestore client."""
    global _firebase_app, _firestore_db
    if not HAS_FIREBASE_SDK:
        return None

    if _firestore_db:
        return _firestore_db

    try:
        if not firebase_admin._apps:
            bucket_name = os.environ.get("FIREBASE_STORAGE_BUCKET", DEFAULT_STORAGE_BUCKET)
            cred_json_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
            
            if cred_json_env:
                cred_dict = json.loads(cred_json_env)
                cred = credentials.Certificate(cred_dict)
            else:
                cred_path = get_firebase_credentials_path()
                if not cred_path:
                    return None
                cred = credentials.Certificate(cred_path)

            _firebase_app = firebase_admin.initialize_app(cred, {
                'storageBucket': bucket_name
            })
            print(f"🔥 [FIREBASE SUCCESS] Connected to Firebase Firestore Project successfully!")

        _firestore_db = firestore.client()
        return _firestore_db
    except Exception as e:
        print(f"[FIREBASE ERROR] Initialization failed: {e}")
        logging.error(traceback.format_exc())
        return None

def test_firebase_connection():
    """Test connection to Firestore database."""
    db = get_firebase_db()
    if not db:
        return False, "Firebase credentials file (firebase_credentials.json) not found or SDK missing."
    try:
        doc_ref = db.collection('_health_check').document('ping')
        doc_ref.set({'status': 'ok', 'timestamp': datetime.now().isoformat()})
        return True, "Firebase Firestore Connected Successfully"
    except Exception as e:
        err_msg = f"Firebase Connection Failed: {e}"
        print(f"[FIREBASE ERROR] {err_msg}")
        return False, err_msg

# Alias for backward compatibility
test_supabase_connection = test_firebase_connection
get_supabase_client = get_firebase_db

# ---------------------------------------------------------------------------
# FIRESTORE DATABASE EXECUTION ENGINE & PROXY BUILDERS
# ---------------------------------------------------------------------------

class FirebaseResponse:
    def __init__(self, data):
        self.data = data or []

class FirebaseQueryBuilder:
    def __init__(self, table_name, columns="*"):
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
        res_data = firestore_query(self.table_name, self.columns, self.filters, self.order_by, self.limit_val)
        return FirebaseResponse(res_data)

class FirebaseInsertBuilder:
    def __init__(self, table_name, data):
        self.table_name = table_name
        self.data = data

    def execute(self):
        res_data = firestore_insert(self.table_name, self.data)
        return FirebaseResponse(res_data)

class FirebaseUpsertBuilder:
    def __init__(self, table_name, data):
        self.table_name = table_name
        self.data = data

    def execute(self):
        res_data = firestore_upsert(self.table_name, self.data)
        return FirebaseResponse(res_data)

class FirebaseUpdateBuilder:
    def __init__(self, table_name, data):
        self.table_name = table_name
        self.data = data
        self.filters = []

    def eq(self, column, value):
        self.filters.append(('eq', column, value))
        return self

    def execute(self):
        res_data = firestore_update(self.table_name, self.data, self.filters)
        return FirebaseResponse(res_data)

class FirebaseDeleteBuilder:
    def __init__(self, table_name):
        self.table_name = table_name
        self.filters = []

    def eq(self, column, value):
        self.filters.append(('eq', column, value))
        return self

    def execute(self):
        res_data = firestore_delete(self.table_name, self.filters)
        return FirebaseResponse(res_data)

class FirebaseTableProxy:
    def __init__(self, table_name):
        self.table_name = table_name

    def select(self, columns="*"):
        return FirebaseQueryBuilder(self.table_name, columns)

    def insert(self, data):
        return FirebaseInsertBuilder(self.table_name, data)

    def upsert(self, data):
        return FirebaseUpsertBuilder(self.table_name, data)

    def update(self, data):
        return FirebaseUpdateBuilder(self.table_name, data)

    def delete(self):
        return FirebaseDeleteBuilder(self.table_name)

def db_table(table_name):
    """Primary DB table proxy function pointing to Firestore."""
    return FirebaseTableProxy(table_name)

def firestore_insert(table_name, data):
    db = get_firebase_db()
    items = data if isinstance(data, list) else [data]
    inserted = []
    for item in items:
        item_copy = dict(item)
        doc_id = item_copy.get('id') or item_copy.get('key')
        if db:
            if doc_id:
                db.collection(table_name).document(str(doc_id)).set(item_copy)
            else:
                ref = db.collection(table_name).add(item_copy)
                item_copy['id'] = ref[1].id
        inserted.append(item_copy)
    return inserted

def firestore_upsert(table_name, data):
    db = get_firebase_db()
    items = data if isinstance(data, list) else [data]
    upserted = []
    for item in items:
        item_copy = dict(item)
        doc_id = item_copy.get('id') or item_copy.get('key')
        if db:
            if doc_id:
                db.collection(table_name).document(str(doc_id)).set(item_copy, merge=True)
            else:
                ref = db.collection(table_name).add(item_copy)
                item_copy['id'] = ref[1].id
        upserted.append(item_copy)
    return upserted

def firestore_query(table_name, columns="*", filters=None, order_by=None, limit_val=None):
    db = get_firebase_db()
    if not db:
        return []

    results = []

    # Optimization: If filtering by ID equality directly, try single doc fetch
    id_filter_val = None
    if filters:
        for op, col, val in filters:
            if op == 'eq' and col == 'id' and val:
                id_filter_val = str(val).strip()
                break

    if id_filter_val:
        try:
            doc_snap = db.collection(table_name).document(id_filter_val).get()
            if doc_snap.exists:
                item = doc_snap.to_dict() or {}
                if 'id' not in item:
                    item['id'] = doc_snap.id
                return [item]
        except Exception as e_single:
            logging.warning(f"[FIRESTORE SINGLE DOC FETCH WARNING {table_name}] {e_single}")

    try:
        col_ref = db.collection(table_name)
        docs = col_ref.stream()
        for d in docs:
            item = d.to_dict() or {}
            if 'id' not in item:
                item['id'] = d.id
            
            match = True
            if filters:
                for op, col, val in filters:
                    r_val = item.get(col)
                    if op == 'eq' and str(r_val or '').lower() != str(val or '').lower():
                        match = False
                    elif op == 'neq' and str(r_val or '').lower() == str(val or '').lower():
                        match = False
                    elif op == 'lte' and str(r_val or '') > str(val or ''):
                        match = False
                    elif op == 'gte' and str(r_val or '') < str(val or ''):
                        match = False
                    elif op == 'lt' and str(r_val or '') >= str(val or ''):
                        match = False
                    elif op == 'in':
                        vals_str = [str(v).lower() for v in (val if isinstance(val, (list, tuple)) else [val])]
                        if str(r_val or '').lower() not in vals_str:
                            match = False
            if match:
                results.append(item)
    except Exception as e_stream:
        logging.error(f"[FIRESTORE QUERY EXCEPTION {table_name}] {e_stream}")

    if order_by:
        col, desc = order_by
        results.sort(key=lambda x: str(x.get(col, '')), reverse=desc)

    if limit_val:
        results = results[:limit_val]

    return results

def firestore_update(table_name, data, filters):
    db = get_firebase_db()
    if not db:
        return []

    updated = []
    try:
        col_ref = db.collection(table_name)
        docs = col_ref.stream()
        for d in docs:
            item = d.to_dict() or {}
            if 'id' not in item or not item['id']:
                item['id'] = d.id

            match = True
            if filters:
                for op, col, val in filters:
                    if op == 'eq' and str(item.get(col) or '').lower() != str(val or '').lower():
                        match = False
            if match:
                d.reference.update(data)
                item.update(data)
                updated.append(item)
    except Exception as e_upd:
        logging.error(f"[FIRESTORE UPDATE EXCEPTION {table_name}] {e_upd}")

    return updated

def firestore_delete(table_name, filters):
    db = get_firebase_db()
    if not db:
        return []

    deleted = []
    try:
        col_ref = db.collection(table_name)
        docs = col_ref.stream()
        for d in docs:
            item = d.to_dict() or {}
            if 'id' not in item or not item['id']:
                item['id'] = d.id

            match = True
            if filters:
                for op, col, val in filters:
                    if op == 'eq' and str(item.get(col) or '').lower() != str(val or '').lower():
                        match = False
                    elif op == 'neq' and str(item.get(col) or '').lower() == str(val or '').lower():
                        match = False
                    elif op == 'in':
                        vals_str = [str(v).lower() for v in (val if isinstance(val, (list, tuple)) else [val])]
                        if str(item.get(col) or '').lower() not in vals_str:
                            match = False
            if match:
                d.reference.delete()
                deleted.append(item)
    except Exception as e_del:
        logging.error(f"[FIRESTORE DELETE EXCEPTION {table_name}] {e_del}")

    return deleted

# ---------------------------------------------------------------------------
# DOCUMENT VAULT FILE STORAGE ENGINE
# ---------------------------------------------------------------------------

def upload_to_firebase_storage(file_obj, filename, category="Other Documents", firm_id="BCWA-MED-000001", pharmacist_name=None, mime_type=None):
    """
    Uploads a document to Firebase Storage or Local Document Vault
    """
    firm_folder = (firm_id or 'BCWA-MED-000001').strip().upper()
    cat_key = (category or '').strip().lower()
    folder_category = CATEGORY_FOLDER_MAP.get(cat_key, 'Other')
    clean_filename = os.path.basename(filename or 'document.pdf')

    if pharmacist_name:
        clean_ph = re.sub(r'[^a-zA-Z0-9_-]', '_', pharmacist_name.strip())
        file_path = f"MedicalStores/{firm_folder}/Pharmacists/{clean_ph}/{folder_category}/{clean_filename}"
    else:
        file_path = f"MedicalStores/{firm_folder}/{folder_category}/{clean_filename}"

    if not mime_type:
        fn_lower = clean_filename.lower()
        if fn_lower.endswith('.pdf'):
            mime_type = 'application/pdf'
        elif fn_lower.endswith('.png'):
            mime_type = 'image/png'
        elif fn_lower.endswith(('.jpg', '.jpeg')):
            mime_type = 'image/jpeg'
        else:
            mime_type = 'application/pdf'

    if hasattr(file_obj, 'read'):
        content = file_obj.read()
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
    elif isinstance(file_obj, str):
        content = file_obj.encode('utf-8')
    else:
        content = file_obj

    if not isinstance(content, bytes):
        content = bytes(content)

    # Save to static/docs directory for fast local preview
    static_docs_dir = os.path.join(os.path.dirname(__file__), 'static', 'docs')
    os.makedirs(static_docs_dir, exist_ok=True)
    local_file_path = os.path.join(static_docs_dir, clean_filename)
    try:
        with open(local_file_path, 'wb') as f:
            f.write(content)
    except Exception as e_write:
        print(f"[LOCAL FILE SAVE NOTICE] {e_write}")

    preview_url = f"/static/docs/{clean_filename}"

    db = get_firebase_db()
    if not (HAS_FIREBASE_SDK and db):
        return {
            'success': False,
            'error': 'Firebase Storage SDK is uninitialized or unavailable.'
        }

    try:
        bucket = storage.bucket()
        blob = bucket.blob(file_path)
        blob.upload_from_string(content, content_type=mime_type)

        encoded_path = urllib.parse.quote(file_path, safe='')
        media_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{encoded_path}?alt=media"

        try:
            blob.make_public()
            preview_url = blob.public_url
        except Exception:
            preview_url = media_url

        return {
            'success': True,
            'url': media_url,
            'public_url': preview_url,
            'bucket': bucket.name,
            'path': file_path
        }
    except Exception as e_upload:
        logging.error(f"[FIREBASE STORAGE UPLOAD FAILURE] {e_upload}")
        return {
            'success': False,
            'error': f"Firebase Storage upload failed: {str(e_upload)}",
            'path': file_path
        }

upload_to_supabase_storage = upload_to_firebase_storage

def download_from_firebase_storage(file_path, bucket_name=None):
    """
    Downloads raw file bytes from Firebase Storage.
    Returns bytes or None if unavailable.
    """
    if not file_path:
        return None

    clean_path = str(file_path).lstrip('/')
    for prefix in ['bcwa-documents/', 'documents/']:
        if clean_path.startswith(prefix):
            clean_path = clean_path[len(prefix):]

    db = get_firebase_db()
    if HAS_FIREBASE_SDK and db:
        try:
            b_name = bucket_name or DEFAULT_STORAGE_BUCKET
            bucket = storage.bucket(b_name)
            blob = bucket.blob(clean_path)
            if blob.exists():
                return blob.download_as_bytes()
        except Exception as e:
            logging.warning(f"[FIREBASE DOWNLOAD WARNING] Could not download '{clean_path}' from bucket: {e}")

    # Fallback: check static/docs directory
    clean_filename = os.path.basename(clean_path)
    static_path = os.path.join(os.path.dirname(__file__), 'static', 'docs', clean_filename)
    if os.path.exists(static_path):
        try:
            with open(static_path, 'rb') as f:
                return f.read()
        except Exception:
            pass

    return None

def delete_from_firebase_storage(file_path, bucket_name=None):
    """Deletes a file from Firebase Storage."""
    if not file_path:
        return False
    clean_path = str(file_path).lstrip('/')
    db = get_firebase_db()
    if HAS_FIREBASE_SDK and db:
        try:
            b_name = bucket_name or DEFAULT_STORAGE_BUCKET
            bucket = storage.bucket(b_name)
            blob = bucket.blob(clean_path)
            if blob.exists():
                blob.delete()
                return True
        except Exception as e:
            logging.warning(f"[FIREBASE DELETE WARNING] {e}")
    return False

delete_from_supabase_storage = delete_from_firebase_storage

def generate_firebase_preview_url(file_path, bucket_name=None):
    """Generates preview URL for document."""
    if not file_path:
        return "/static/docs/sample.pdf"
    clean_path = str(file_path).lstrip('/')
    if clean_path.startswith("http://") or clean_path.startswith("https://"):
        return clean_path
    b_name = bucket_name or DEFAULT_STORAGE_BUCKET
    encoded_path = urllib.parse.quote(clean_path, safe='')
    return f"https://firebasestorage.googleapis.com/v0/b/{b_name}/o/{encoded_path}?alt=media"

generate_document_preview_url = generate_firebase_preview_url
