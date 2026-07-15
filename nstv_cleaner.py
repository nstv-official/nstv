import requests
import json
import concurrent.futures
import os
import shutil
from datetime import datetime
from urllib.parse import urlparse

# =================================================================
# DAFTAR FILE YANG AKAN DIBERSIHKAN & PENGATURAN BACKUP
# =================================================================
FILES_TO_CLEAN = ["system_config_v3.data"]
BACKUP_DIR = "backup_NSTV"
TIMEOUT = 12

def create_backup(filename):
    """Membuat cadangan file playlist sebelum dimodifikasi."""
    if not os.path.exists(filename):
        return False
    try:
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_part, ext_part = os.path.splitext(filename)
        backup_path = os.path.join(BACKUP_DIR, f"{name_part}_backup_{timestamp}{ext_part}")
        shutil.copy2(filename, backup_path)
        print(f"[✓] Backup berhasil dibuat: {backup_path}")
        return True
    except Exception as e:
        print(f"[X] Gagal membuat backup: {e}")
        return False

def get_smart_headers(url, item):
    """
    Menyusun header pintar dengan memprioritaskan data asli di JSON channel,
    lalu digabungkan dengan logika anti-blocking Android.
    """
    # 1. Tentukan User-Agent (Prioritas bawaan item)
    ua = item.get("user_agent") or "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
    headers = {"User-Agent": ua}

    # 2. Ambil data headers bawaan dari database JSON jika ada
    item_headers = item.get("headers", {})
    if isinstance(item_headers, dict):
        for key, val in item_headers.items():
            if val:
                headers[key] = val

    # 3. Logika Tambahan Otomatis jika headers bawaan kosong
    domain = urlparse(url).netloc.lower()
    if "visionplus.id" in domain or "cloudfront.net" in domain:
        if "Origin" not in headers:
            headers["Origin"] = "https://www.visionplus.id"
        if "Referer" not in headers:
            headers["Referer"] = "https://www.visionplus.id/"
        headers.update({
            "X-Requested-With": "id.visionplus.android",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Dest": "empty"
        })
        
    return headers

def check_link(item):
    """Mengecek keaktifan link dengan toleransi Geoblocking khusus GitHub Actions."""
    url = item.get("uri") or item.get("streamUrl") or item.get("url")
    if not url:
        return item

    headers = get_smart_headers(url, item)

    # Coba verifikasi dengan 2 metode (HEAD terlebih dahulu, lalu GET jika gagal)
    try:
        # Metode 1: HEAD request (cepat dan tidak membebani server)
        response = requests.head(url, headers=headers, timeout=TIMEOUT, allow_redirects=True)
        
        # Toleransi khusus IP luar negeri (GitHub): Jika 403 (Forbidden) atau 451 (Geoblock), amankan channel!
        if response.status_code in:
            print(f"[!] Geoblock Terdeteksi ({response.status_code}) pada: {item.get('title')} -> Dipertahankan")
            return item
            
        if response.status_code < 400:
            return item
            
    except:
        pass

    try:
        # Metode 2: GET request (Jika server menolak metode HEAD)
        response = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True, allow_redirects=True)
        
        if response.status_code in:
            print(f"[!] Geoblock Terdeteksi ({response.status_code}) pada: {item.get('title')} -> Dipertahankan")
            return item
            
        if response.status_code < 400:
            return item
    except:
        pass

    # Jika benar-benar timeout atau merespon 404/500 ke atas, tandai mati
    print(f"[-] Link MATI/RTO: {item.get('title')}")
    return None

def process_file(filename):
    print(f"--- Memproses File: {filename} ---")
    
    if not create_backup(filename):
        print(f"[!] Pembersihan {filename} dibatalkan karena backup gagal.\n")
        return

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
        # Batasi max_workers ke 10 agar server IPTV tidak mencurigai spam request dari GitHub
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(check_link, items))
            valid_items = [i for i in results if i is not None]

    except Exception as e:
        print(f"Error baca {filename}: {e}")
        return

    if len(items) > 0 and len(valid_items) == 0:
        print(f"Peringatan: Semua link dianggap mati (Kemungkinan internet server putus). Data TIDAK diubah.")
        return

    # Urutkan kembali ID dari angka 1 secara rapi
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
    print("Memulai NSTV CLEANER V3 PRO (GitHub Actions Optimized)...\n")
    for file in FILES_TO_CLEAN:
        process_file(file)
