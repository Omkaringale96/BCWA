import os
import json
import logging

try:
    import firebase_admin
    from firebase_admin import credentials, firestore, storage
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

FIREBASE_BUCKET_NAME = os.environ.get('FIREBASE_STORAGE_BUCKET', 'bcwa-portal.appspot.com')
STORAGE_FOLDER = os.environ.get('FIREBASE_STORAGE_FOLDER', 'BCWA_Portal_Documents')

db_firestore = None
bucket_storage = None

def init_firebase():
    global db_firestore, bucket_storage
    if not HAS_FIREBASE:
        return None

    if db_firestore:
        return db_firestore

    cred_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
    cred_file = os.environ.get('FIREBASE_CREDENTIALS_FILE', 'firebase_key.json')

    try:
        if not firebase_admin._apps:
            options = {'storageBucket': FIREBASE_BUCKET_NAME}
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred, options)
            elif os.path.exists(cred_file):
                cred = credentials.Certificate(cred_file)
                firebase_admin.initialize_app(cred, options)
            else:
                try:
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred, options)
                except Exception:
                    return None

        db_firestore = firestore.client()
        try:
            bucket_storage = storage.bucket()
        except Exception:
            bucket_storage = None

        return db_firestore
    except Exception as e:
        logging.error(f"Firebase initialization info: {e}")
        return None

def upload_document_to_firebase_storage(file_obj, filename, folder_category="General"):
    """
    Uploads PDFs, scanned documents, photos, signatures directly to Firebase Storage.
    Folder structure: BCWA_Portal_Documents/<category>/<filename>
    """
    db = init_firebase()
    target_path = f"{STORAGE_FOLDER}/{folder_category}/{filename}"

    if bucket_storage:
        try:
            blob = bucket_storage.blob(target_path)
            if hasattr(file_obj, 'read'):
                blob.upload_from_file(file_obj)
            else:
                blob.upload_from_string(file_obj)
            
            try:
                blob.make_public()
                public_url = blob.public_url
            except Exception:
                public_url = f"https://firebasestorage.googleapis.com/v0/b/{FIREBASE_BUCKET_NAME}/o/{target_path.replace('/', '%2F')}?alt=media"

            return {
                'success': True,
                'url': public_url,
                'path': target_path,
                'is_mock': False
            }
        except Exception as e:
            logging.error(f"Firebase Storage upload failed: {e}")

    # Fallback Firebase Storage URL structure if offline/mock
    return {
        'success': True,
        'url': f"https://firebasestorage.googleapis.com/v0/b/{FIREBASE_BUCKET_NAME}/o/{target_path.replace('/', '%2F')}?alt=media",
        'path': target_path,
        'is_mock': True
    }

def sync_to_firestore(collection_name, doc_id, data):
    """
    Syncs store, pharmacist, document, renewal, and user metadata to Firebase Firestore.
    """
    db = init_firebase()
    if not db:
        return False
    try:
        db.collection(collection_name).document(str(doc_id)).set(data, merge=True)
        return True
    except Exception as e:
        logging.error(f"Firestore sync error for {collection_name}/{doc_id}: {e}")
        return False

def get_from_firestore(collection_name, doc_id):
    db = init_firebase()
    if not db:
        return None
    try:
        doc = db.collection(collection_name).document(str(doc_id)).get()
        return doc.to_dict() if doc.exists else None
    except Exception as e:
        logging.error(f"Firestore fetch error: {e}")
        return None
