import requests
import json
import concurrent.futures
import re
import random
from urllib.parse import urlparse

# =================================================================
# KONFIGURASI AGGREGATOR
# =================================================================
SOURCES = [
    "https://raw.githubusercontent.com/uppermoon77/bodyslam/refs/heads/main/BS31AGUSTUS2026",
    "https://raw.githubusercontent.com/apistech/project/main/playlists/events.m3u8",
    "https://raw.githubusercontent.com/dhasap/dhanytv/refs/heads/main/dhanytv.m3u"
]
LOCAL_PLAYLIST = "system_config_v3.data"
TIMEOUT = 12

# Kategori yang di-BLOKIR (Kecuali Sports)
BLACKLIST_GEO = ["MALAYSIA", "SINGAPORE", "SINGAPURA", "CHINA", "INDIA", "USA", "AMERIKA", "BRUNEI", "TAIWAN", "RUSSIA", "RUSIA", "VIETNAM", "THAILAND", "KOREA", "JAPAN"]
# Kategori yang SELALU DI-IZINKAN
WHITELIST_TYPE = ["NASIONAL", "DAERAH", "LOKAL", "RELIGI", "HIBURAN", "MOVIES", "KIDS", "SPORTS"]

# Daftar User-Agent Default (Akan dipilih acak jika sumber M3U tidak menyediakan user-agent khusus)
USER_AGENTS_POOL = [
    "Mozilla/5.0 (Linux; Android 10; BRAVIA 4K Smart TV) AppleWebKit/537.36",
    "ExoPlayerDemo/2.15.1 (Linux; Android 13) ExoPlayerLib/2.15.1",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Mozilla/5.0 (iPhone14,6; U; CPU iPhone OS 15_4 like Mac OS X) AppleWebKit/602.1.50 (KHTML, like Gecko) Version/10.0 Mobile/19E241 Safari/602.1"
]

def get_smart_headers(url, custom_ua=None):
    """Menyusun headers pintar berdasarkan domain dan custom User-Agent jika ada"""
    ua = custom_ua if custom_ua else random.choice(USER_AGENTS_POOL)
    headers = {"User-Agent": ua}
    
    domain = urlparse(url).netloc.lower()
    if "visionplus.id" in domain or "cloudfront.net" in domain:
        headers.update({
            "Origin": "https://visionplus.id",
            "Referer": "https://visionplus.id/",
            "X-Requested-With": "id.visionplus.android"
        })
    return headers

def is_link_alive(url, custom_ua=None):
    """Mengecek status keaktifan URL"""
    if not url:
        return False
    try:
        headers = get_smart_headers(url, custom_ua)
        response = requests.get(url, headers=headers, timeout=TIMEOUT, stream=True, allow_redirects=True)
        return response.status_code < 400
    except:
        return False

def parse_m3u_advanced(content):
    """Menganalisis M3U secara baris-per-baris untuk akurasi data (UA, DRM, Nama, URL)"""
    channels = []
    lines = content.split('\n')
    
    current_extinf = None
    current_ua = None
    current_key = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # 1. Deteksi Baris #EXTINF
        if line.startswith("#EXTINF:"):
            current_extinf = line
            continue
            
        # 2. Deteksi Baris User-Agent Khusus dari M3U
        elif line.startswith("#EXTVLCOPT:http-user-agent="):
            current_ua = line.split("=", 1)[1].strip()
            continue
            
        # 3. Deteksi Baris KODIPROP (DRM Clearkey)
        elif line.startswith("#KODIPROP:status_key=") or line.startswith("#KODIPROP:license_key="):
            current_key = line.split("=", 1)[1].strip()
            continue
            
        # 4. Deteksi Baris URL (Bisa diawali '#' jika di-comment oleh pemiliknya)
        elif line.startswith("http") or (line.startswith("#http") or line.startswith("# https")):
            # Bersihkan url jika ada tanda pagar penonaktif di depannya
            url = re.sub(r'^[#\s]+', '', line).strip()
            
            if current_extinf:
                # Ekstrak Metadata menggunakan Regex
                group_match = re.search(r'group-title="([^"]*)"', current_extinf, re.IGNORECASE)
                logo_match = re.search(r'tvg-logo="([^"]*)"', current_extinf, re.IGNORECASE)
                tvg_id_match = re.search(r'tvg-id="([^"]*)"', current_extinf, re.IGNORECASE)
                tvg_name_match = re.search(r'tvg-name="([^"]*)"', current_extinf, re.IGNORECASE)
                
                # Nama channel berada di paling akhir setelah tanda koma terakhir
                name_parts = current_extinf.split(',')
                name = name_parts[-1].strip() if name_parts else "Unknown"
                
                group = group_match.group(1).upper().strip() if group_match else "LAINNYA"
                logo = logo_match.group(1).strip() if logo_match else ""
                tvg_id = tvg_id_match.group(1).strip() if tvg_id_match else ""
                tvg_name = tvg_name_match.group(1).strip() if tvg_name_match else name

                # FILTER UTAMA
                if "MAINTENANCE" in name.upper() or "ORDER DISINI" in group:
                    # Reset data baris dan lewatin
                    current_extinf = current_ua = current_key = None
                    continue

                is_sports = "SPORTS" in group
                if any(geo in group for geo in BLACKLIST_GEO) and not is_sports:
                    current_extinf = current_ua = current_key = None
                    continue

                if not (any(w in group for w in WHITELIST_TYPE) or is_sports):
                    current_extinf = current_ua = current_key = None
                    continue

                # Gabungkan data ke struktur objek m3u sementara
                channels.append({
                    "title": name,
                    "category": group,
                    "uri": url,
                    "user_agent": current_ua if current_ua else random.choice(USER_AGENTS_POOL),
                    "drm_key": current_key,
                    "tvg_id": tvg_id,
                    "tvg_name": tvg_name,
                    "tvg_logo": logo
                })
                
            # Reset penampung data untuk baris channel berikutnya
            current_extinf = current_ua = current_key = None
            
    return channels

def aggregate():
    print("--- Memulai NSTV Smart Aggregator V3 ---")

    # 1. Muat atau Buat Database Lokal
    try:
        with open(LOCAL_PLAYLIST, 'r', encoding='utf-8') as f:
            local_data = json.load(f)
        local_channels = local_data.get("channels", [])
    except Exception as e:
        print(f"Menginisialisasi file playlist lokal baru.")
        local_data = {"channels": []}
        local_channels = []

    # 2. Ambil & Parse Data Scraper dari Semua Sumber Internet
    source_channels = []
    for url in SOURCES:
        print(f"Membaca internet sumber: {url}")
        try:
            response = requests.get(url, headers={"User-Agent": random.choice(USER_AGENTS_POOL)}, timeout=20)
            parsed = parse_m3u_advanced(response.text)
            source_channels.extend(parsed)
            print(f"-> Berhasil memproses {len(parsed)} channel potensial.")
        except Exception as e:
            print(f"-> Gagal membaca url sumber: {e}")

    # 3. Filter Validasi: Cek Kesehatan Channel Lokal Saat Ini
    # Buang otomatis jika terbukti mati!
    alive_local_channels = []
    if local_channels:
        print("\nMengecek kesehatan link lokal saat ini (Membuang link mati)...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            local_status = list(executor.map(lambda x: is_link_alive(x.get("uri"), x.get("user_agent")), local_channels))
        
        for idx, is_alive in enumerate(local_status):
            if is_alive:
                alive_local_channels.append(local_channels[idx])
            else:
                print(f"[-] Dibuang (Lokal Mati): {local_channels[idx].get('title')}")

    # Map nama lokal yang sukses bertahan agar tidak duplikat saat disisipi data baru
    local_names_set = {c.get("title", "").upper() for c in alive_local_channels}

    # 4. Analisis & Filter Channel Baru dari Internet (Hanya masukkan yang HIDUP)
    new_candidates = [s for s in source_channels if s['title'].upper() not in local_names_set]
    print(f"\nMengecek status keaktifan {len(new_candidates)} calon channel internet baru...")
    
    valid_new_channels = []
    if new_candidates:
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            new_status = list(executor.map(lambda x: is_link_alive(x['uri'], x['user_agent']), new_candidates))
            
        for idx, is_alive in enumerate(new_status):
            cand = new_candidates[idx]
            if is_alive:
                # Susun struktur JSON sesuai template persis permintaan Anda
                headers_data = get_smart_headers(cand['uri'], cand['user_agent'])
                
                # Susun objek JSON terstruktur
                json_struct = {
                    "id": 0, # Akan diurutkan cerdas di langkah akhir
                    "title": cand['title'],
                    "category": cand['category'],
                    "uri": cand['uri'],
                    "user_agent": cand['user_agent'],
                    "is_live": True,
                    "match_id": "",
                    "headers": {
                        "Referer": headers_data.get("Referer", ""),
                        "Origin": headers_data.get("Origin", "")
                    },
                    "drm_info": {
                        "is_protected": True if cand['drm_key'] else False,
                        "drm_type": "clearkey" if cand['drm_key'] else "",
                        "drm_key": cand['drm_key'] if cand['drm_key'] else ""
                    },
                    "epg_metadata": {
                        "tvg_id": cand['tvg_id'],
                        "tvg_name": cand['tvg_name'],
                        "tvg_logo": cand['tvg_logo'],
                        "source_xml": ""
                    }
                }
                valid_new_channels.append(json_struct)
