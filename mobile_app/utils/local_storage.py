import json
import os

# Flet অ্যাপ যখন অ্যান্ড্রয়েডে চলে, তখন এটি FLET_APP_DATA_DIR সেট করে
# যা অ্যাপের নিজস্ব ডেটা ডিরেক্টরিকে নির্দেশ করে।
# যদি এই ভ্যারিয়েবল না থাকে (ডেস্কটপে চলার সময়), তাহলে আগের মতো হোম ডিরেক্টরি ব্যবহার করবে।
APP_DATA_DIR = os.getenv("FLET_APP_DATA_DIR")

if APP_DATA_DIR:
    # অ্যান্ড্রয়েড বা iOS-এর জন্য অ্যাপের নিজস্ব ফোল্ডার ব্যবহার করা হচ্ছে
    CACHE_DIR = os.path.join(APP_DATA_DIR, ".shrutipaath_cache")
else:
    # ডেস্কটপের জন্য ইউজারের হোম ডিরেক্টরি ব্যবহার করা হচ্ছে
    CACHE_DIR = os.path.join(os.path.expanduser("~"), ".shrutipaath_cache")

# নিশ্চিত করা হচ্ছে যে ডিরেক্টরিগুলো তৈরি আছে
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

DOWNLOADS_DIR = os.path.join(CACHE_DIR, "downloads")
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)


def get_cache_path(key):
    """Returns the full path for a given cache key."""
    return os.path.join(CACHE_DIR, f"{key}.json")

def save_data(key, data):
    """Saves data (dictionary or list) to a local JSON file."""
    try:
        path = get_cache_path(key)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"Error saving data for '{key}': {e}")
        return False

def load_data(key):
    """Loads data from a local JSON file."""
    path = get_cache_path(key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading data for '{key}': {e}")
        return None

def get_download_path(filename):
    """Gets the path for a downloaded audio file."""
    return os.path.join(DOWNLOADS_DIR, filename)

def is_downloaded(url):
    """Checks if an audio file from a URL is already downloaded."""
    if not url: return False
    filename = url.split('/')[-1].split('?')[0]
    return os.path.exists(get_download_path(filename))

def get_local_url(url):
    """Returns the local file path for a downloaded audio file."""
    if not url: return None
    filename = url.split('/')[-1].split('?')[0]
    return get_download_path(filename)