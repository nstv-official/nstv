import requests
import json
import concurrent.futures
from urllib.parse import urlparse

# =================================================================
# DAFTAR FILE YANG AKAN DIBERSIHKAN
# Catatan: Pastikan file JSON berada di folder yang sama dengan script ini.
# =================================================================
FILES_TO_CLEAN = ["playlist.json", "voli.json"]
TIMEOUT = 12

def get_headers(url):
    """
    Menyamakan logika header dengan MainViewModel.kt di Android.
    Menghindari blokir (403 Forbidden) pada domain tertentu.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
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
    Mengecek keaktifan link.
    Mendukung key 'uri' (standar Android) atau 'streamUrl'.
    """
    # Mencari URL dengan prioritas: uri -> streamUrl -> url
    url = item.get("uri") or item.get("streamUrl") or item.get("url")

    if not url:
        return item

    try:
        headers = get_headers(url)
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
        print(f"Peringatan: Semua link di {filename} dianggap mati. Data TIDAK diubah.")
        return

    if is_obj_format:
        data["channels"] = valid_items
    else:
        data = valid_items

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Pembersihan {filename} Selesai. Item aktif: {len(valid_items)}\n")

if __name__ == "__main__":
    print("Memulai NSTV CLEANER V3 (Sesuai Logika Android)...\n")
    for file in FILES_TO_CLEAN:
        process_file(file)
