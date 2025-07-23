import os
import requests
from . import local_storage
from google.cloud import firestore
from google.oauth2 import service_account

db = None

def initialize_firestore():
    """Initializes the Firestore client using the service account key."""
    global db
    if db:
        return True
    try:
        # APK-তে ফাইলটি অ্যাপের ভেতরে থাকবে। তাই পাথ পরিবর্তন করা হলো।
        # os.path.dirname(__file__) -> /utils/
        # os.path.join(..., "..") -> /mobile_app/
        cred_path = os.path.join(os.path.dirname(__file__), "..", "service_account.json")
        
        if not os.path.exists(cred_path):
            print(f"Service account file not found at {cred_path}")
            return False
            
        credentials = service_account.Credentials.from_service_account_file(cred_path)
        db = firestore.Client(credentials=credentials)
        print("Firestore client initialized successfully.")
        return True
    except Exception as e:
        print(f"Error initializing Firestore: {e}")
        return False

def get_app_data():
    """
    Main function to get data. Tries online first, then falls back to offline cache.
    """
    if initialize_firestore():
        try:
            print("Fetching data from remote server (Firestore)...")
            # শুধুমাত্র সক্রিয় বিষয়গুলো আনা হচ্ছে
            subjects_ref = db.collection('subjects').where('is_active', '==', True).order_by('order').stream()
            subjects = [doc.to_dict() for doc in subjects_ref]
            
            config_doc = db.collection('config').document('app_settings').get()
            config = config_doc.to_dict() if config_doc.exists else {}

            if subjects or config:
                print("Data fetched and cached.")
                local_storage.save_data('subjects', subjects)
                local_storage.save_data('config', config)
                return subjects, config
        except Exception as e:
            print(f"Could not fetch from Firestore: {e}. Falling back to local cache.")
    
    print("Loading data from local cache.")
    subjects = local_storage.load_data('subjects')
    config = local_storage.load_data('config')
    
    return subjects, config

def download_audio(url, progress_callback):
    """Downloads an audio file and saves it locally, with progress updates."""
    try:
        filename = url.split('/')[-1].split('?')[0]
        local_path = local_storage.get_download_path(filename)
        
        response = requests.get(url, stream=True)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        bytes_downloaded = 0
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                bytes_downloaded += len(chunk)
                progress = (bytes_downloaded / total_size) if total_size > 0 else 0
                progress_callback(progress)
        
        print(f"Downloaded {filename} to {local_path}")
        return local_path
    except Exception as e:
        print(f"Failed to download {url}: {e}")
        return None