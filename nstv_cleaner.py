import requests
import json
import concurrent.futures
from urllib.parse import urlparse

# =================================================================
# DAFTAR FILE YANG AKAN DIBERSIHKAN
# =================================================================
FILES_TO_CLEAN = ["system_config_v3.data"]
TIMEOUT = 12

def get_headers(url, custom_ua=None):
    """
    Menyamakan logika header dengan MainViewModel.kt di Android.
    Menghindari blokir (403 Forbidden) pada domain tertentu.
    """
    # Jika channel memiliki user_agent khusus, gunakan itu. Jika tidak, pakai default.
    ua = custom_ua if custom_ua else "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
    
    headers = {
        "User-Agent": ua
    }

    domain = urlparse(url).netloc.lower()

    # Logika khusus untuk VisionPlus/Cloudfront
    if "visionplus.id" in domain or "cloudfront.net" in domain:
        headers.update({
            "Origin": "https://www.visionplus.id",
            "Referer": "https://www.visionplus.id/",
            "X-Requested-With": "id.visionplus.android",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Dest": "empty"
        })
    return headers

def check_link(item):
    """
    Mengecek keaktifan link dengan mendukung User-Agent spesifik milik channel.
    Mendukung key 'uri' (standar Android) atau 'streamUrl'.
    """
    # Mencari URL dengan prioritas: uri -> streamUrl -> url
    url = item.get("uri") or item.get("streamUrl") or item.get("url")

    if not url:
        return item

    try:
        # Mengambil custom user_agent dari data channel jika ada
        custom_ua = item.get("user_agent")
        headers = get_headers(url, custom_ua)
        
        # Gunakan stream=True agar hemat kuota
        response = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True, allow_redirects=True)

        # Jika status code di bawah 400, link HIDUP
        if response.status_code < 400:
            return item
    except:
        pass

    return None

def process_file(filename):
    print(f"--- Memproses File: {filename} ---")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        is_obj_format = isinstance(data, dict) and "channels" in data
        items = data["channels"] if is_obj_format else data

        if not isinstance(items, list):
            print(f"Format {filename} tidak dikenali, melewati...")
            return

        print(f"Mengecek {len(items)} item di {filename}...")

        valid_items = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
            results = list(executor.map(check_link, items))
            valid_items = [i for i in results if i is not None]

    except Exception as e:
        print(f"Error baca {filename}: {e}")
        return

    if len(items) > 0 and len(valid_items) == 0:
        print(f"Peringatan: Semua link di {filename} dianggap mati. Data TIDAK diubah untuk keamanan.")
        return

    # Fitur Cerdas: Mengurutkan kembali ID secara berurutan setelah ada channel yang dihapus
    for index, item in enumerate(valid_items, start=1):
        if "id" in item:
            item["id"] = index

    if is_obj_format:
        data["channels"] = valid_items
    else:
        data = valid_items

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Pembersihan {filename} Selesai.")
    print(f"Item aktif tersisa: {len(valid_items)} (ID telah diurutkan ulang)\n")

if __name__ == "__main__":
    print("Memulai NSTV CLEANER V3 + Smart Auto-ID (Sesuai Logika Android)...\n")
    for file in FILES_TO_CLEAN:
        process_file(file)
