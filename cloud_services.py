import os
import json
import logging

# -----------------------------------------------------------------------------
# CLOUDINARY FILE & DOCUMENT UPLOADER
# -----------------------------------------------------------------------------
try:
    import cloudinary
    import cloudinary.uploader
    HAS_CLOUDINARY = True
except ImportError:
    HAS_CLOUDINARY = False

CLOUDINARY_FOLDER = os.environ.get('CLOUDINARY_FOLDER', 'BCWA_Portal_Documents')

def init_cloudinary():
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME')
    api_key = os.environ.get('CLOUDINARY_API_KEY')
    api_secret = os.environ.get('CLOUDINARY_API_SECRET')

    if HAS_CLOUDINARY and cloud_name and api_key and api_secret:
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True
        )
        return True
    return False

def upload_document_to_cloudinary(file_obj, filename, folder_category="General"):
    """
    Uploads a document (PDF, image, PNG, JPG) to Cloudinary into the single BCWA folder.
    Returns: dict with 'url', 'public_id', 'format', 'bytes'
    """
    if not init_cloudinary():
        # Fallback local URL representation if Cloudinary credentials are not set
        target_folder = f"{CLOUDINARY_FOLDER}/{folder_category}"
        return {
            'success': True,
            'url': f"https://res.cloudinary.com/bcwa-portal/image/upload/v1722880000/{target_folder}/{filename}",
            'public_id': f"{target_folder}/{filename}",
            'format': filename.split('.')[-1] if '.' in filename else 'pdf',
            'folder': target_folder,
            'is_mock': True
        }

    try:
        full_folder = f"{CLOUDINARY_FOLDER}/{folder_category}"
        response = cloudinary.uploader.upload(
            file_obj,
            folder=full_folder,
            use_filename=True,
            unique_filename=True,
            resource_type="auto"
        )
        return {
            'success': True,
            'url': response.get('secure_url'),
            'public_id': response.get('public_id'),
            'format': response.get('format'),
            'bytes': response.get('bytes'),
            'folder': full_folder,
            'is_mock': False
        }
    except Exception as e:
        logging.error(f"Cloudinary upload failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

# -----------------------------------------------------------------------------
# FIREBASE FIRESTORE DATABASE SYNCHRONIZER
# -----------------------------------------------------------------------------
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    HAS_FIREBASE = True
except ImportError:
    HAS_FIREBASE = False

db_firestore = None

def init_firebase():
    global db_firestore
    if not HAS_FIREBASE:
        return None

    if db_firestore:
        return db_firestore

    cred_json = os.environ.get('FIREBASE_SERVICE_ACCOUNT_JSON')
    cred_file = os.environ.get('FIREBASE_CREDENTIALS_FILE', 'firebase_key.json')

    try:
        if not firebase_admin._apps:
            if cred_json:
                cred_dict = json.loads(cred_json)
                cred = credentials.Certificate(cred_dict)
                firebase_admin.initialize_app(cred)
            elif os.path.exists(cred_file):
                cred = credentials.Certificate(cred_file)
                firebase_admin.initialize_app(cred)
            else:
                # Default application credentials fallback
                try:
                    cred = credentials.ApplicationDefault()
                    firebase_admin.initialize_app(cred)
                except Exception:
                    return None

        db_firestore = firestore.client()
        return db_firestore
    except Exception as e:
        logging.error(f"Firebase initialization info: {e}")
        return None

def sync_to_firestore(collection_name, doc_id, data):
    """
    Syncs a record to Firebase Firestore.
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
