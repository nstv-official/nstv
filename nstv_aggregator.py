import requests
import json
import concurrent.futures
import re
from urllib.parse import urlparse

# =================================================================
# KONFIGURASI AGGREGATOR
# =================================================================
SOURCES = [
    "https://raw.githubusercontent.com/uppermoon77/bodyslam/refs/heads/main/BS31AGUSTUS2026",
    "https://raw.githubusercontent.com/dhasap/dhanytv/refs/heads/main/dhanytv.m3u"
]
LOCAL_PLAYLIST = "system_config_v3.data"
TIMEOUT = 12

# Kategori yang di-BLOKIR (Kecuali Sports)
BLACKLIST_GEO = ["MALAYSIA", "SINGAPORE", "SINGAPURA", "CHINA", "INDIA", "USA", "AMERIKA", "BRUNEI", "TAIWAN", "RUSSIA", "RUSIA", "VIETNAM", "THAILAND", "KOREA", "JAPAN"]
# Kategori yang SELALU DI-IZINKAN
WHITELIST_TYPE = ["NASIONAL", "DAERAH", "LOKAL", "RELIGI", "HIBURAN", "MOVIES", "KIDS", "SPORTS"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
}

def get_headers_for_url(url):
    headers = HEADERS.copy()
    domain = urlparse(url).netloc.lower()
    if "visionplus.id" in domain or "cloudfront.net" in domain:
        headers.update({
            "Origin": "https://www.visionplus.id",
            "Referer": "https://www.visionplus.id/",
            "X-Requested-With": "id.visionplus.android"
        })
    return headers

def is_link_alive(url):
    try:
        headers = get_headers_for_url(url)
        response = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True, allow_redirects=True)
        return response.status_code < 400
    except:
        return False

def parse_m3u(content):
    channels = []
    # Regex untuk mengambil metadata M3U
    items = re.findall(r'#EXTINF:.*group-title="([^"]*)".*tvg-logo="([^"]*)".*,(.*)\n(?:#KODIPROP:.*license_key=(.*)\n)?(.*)', content)

    for group, logo, name, key, url in items:
        group = group.upper().strip()
        name = name.strip()
        url = url.strip()

        # FILTER 1: Lewati jika maintenance
        if "MAINTENANCE" in name.upper() or "ORDER DISINI" in group:
            continue

        # FILTER 2: Geografis (Hanya blokir jika bukan kategori SPORTS)
        is_sports = "SPORTS" in group
        is_blacklisted = any(geo in group for geo in BLACKLIST_GEO)

        if is_blacklisted and not is_sports:
            continue

        # FILTER 3: Hanya ambil Whitelist atau Sports
        is_whitelisted = any(w in group for w in WHITELIST_TYPE)
        if not (is_whitelisted or is_sports):
            continue

        channels.append({
            "title": name,
            "category": group,
            "uri": url,
            "logo": logo,
            "drm_key": key.strip() if key else None
        })
    return channels

def aggregate():
    print("--- Memulai NSTV Aggregator & Smart Link Repair ---")

    # 1. Baca Playlist Lokal
    try:
        with open(LOCAL_PLAYLIST, 'r', encoding='utf-8') as f:
            local_data = json.load(f)
        local_channels = local_data.get("channels", [])
    except Exception as e:
        print(f"Error baca playlist lokal: {e}")
        return

    # 2. Ambil Playlist Sumber (M3U)
    print(f"Mengambil data dari sumber: {SOURCE_URL}")
    try:
        response = requests.get(SOURCE_URL, headers=HEADERS, timeout=20)
        source_channels = parse_m3u(response.text)
        print(f"Ditemukan {len(source_channels)} channel potensial di sumber.")
    except Exception as e:
        print(f"Gagal mengambil sumber: {e}")
        return

    # 3. Identifikasi Channel yang MATI di NSTV
    print("Mengecek kesehatan playlist NSTV saat ini...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        status_results = list(executor.map(lambda x: is_link_alive(x.get("uri", "")), local_channels))

    updated_count = 0
    new_added_count = 0

    # 4. Proses Perbaikan & Penambahan
    for i, is_alive in enumerate(status_results):
        if not is_alive:
            target_name = local_channels[i].get("title", "")
            print(f"Mencoba memperbaiki channel MATI: {target_name}")

            # Cari pengganti di sumber
            match = next((s for s in source_channels if s['title'].upper() == target_name.upper()), None)
            if match and is_link_alive(match['uri']):
                local_channels[i]['uri'] = match['uri']
                if match['drm_key']:
                    local_channels[i]['drm_info'] = {"is_protected": True, "drm_type": "clearkey", "drm_key": match['drm_key']}
                print(f"  > BERHASIL diperbaiki dengan link baru!")
                updated_count += 1

    # 5. Tambahkan Channel Baru yang belum ada (Opsional: Hanya yang Hidup)
    local_names = {c.get("title", "").upper() for c in local_channels}
    new_candidates = [s for s in source_channels if s['title'].upper() not in local_names]

    print(f"Mengecek {len(new_candidates)} calon channel baru...")
    if new_candidates:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            new_alive_results = list(executor.map(lambda x: is_link_alive(x['uri']), new_candidates))

        for i, is_alive in enumerate(new_alive_results):
            if is_alive:
                cand = new_candidates[i]
                new_item = {
                    "title": cand['title'],
                    "category": cand['category'],
                    "uri": cand['uri'],
                    "epg_metadata": {"tvg_logo": cand['logo']},
                    "is_live": True
                }
                if cand['drm_key']:
                    new_item["drm_info"] = {"is_protected": True, "drm_type": "clearkey", "drm_key": cand['drm_key']}

                local_channels.append(new_item)
                new_added_count += 1

    # 6. Simpan Hasil Akhir
    local_data["channels"] = local_channels
    with open(LOCAL_PLAYLIST, 'w', encoding='utf-8') as f:
        json.dump(local_data, f, indent=2, ensure_ascii=False)

    print(f"\n--- Selesai ---")
    print(f"Channel diperbaiki: {updated_count}")
    print(f"Channel baru ditambahkan: {new_added_count}")
    print(f"Total channel sekarang: {len(local_channels)}")

if __name__ == "__main__":
    aggregate()
