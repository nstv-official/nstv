import json
import re
from urllib.parse import urlparse
import requests

def check_url_status(url, user_agent, headers_dict):
    """
    Fungsi untuk mengecek apakah URL video masih aktif atau sudah mati.
    Menggunakan HTTP HEAD agar hemat kuota dan proses verifikasi berjalan cepat.
    """
    custom_headers = {
        "User-Agent": user_agent,
        "Referer": headers_dict.get("Referer", ""),
        "Origin": headers_dict.get("Origin", "")
    }
    try:
        # Melakukan HTTP HEAD request dengan timeout 3 detik demi efisiensi waktu
        response = requests.head(url, headers=custom_headers, timeout=3, allow_redirects=True)
        # Jika status code 200, artinya link aktif dan siap diputar
        if response.status_code == 200:
            return True
        else:
            print(f"   [MATI] Status {response.status_code} untuk URL: {url}")
            return False
    except requests.RequestException:
        print(f"   [MATI] Timeout/Gagal tersambung ke URL: {url}")
        return False

def parse_and_validate_m3u(input_text):
    raw_blocks = re.split(r'\n\s*\+\s*\+\s*\+\s*\+\s*\n|\n\s*\n', input_text)
    temporary_channels = []
    
    for block in raw_blocks:
        block = block.strip()
        if not block or "#EXTINF" not in block:
            continue
            
        lines = block.split('\n')
        
        license_type = ""
        license_key = ""
        referrer = ""
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"
        tvg_id = ""
        tvg_name = ""
        tvg_logo = ""
        group_title = "NASIONAL"
        title = "Unknown Channel"
        urls = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            if "license_type" in line:
                license_type = line.split('=')[-1].replace("org.w3.", "").strip()
            elif "license_key" in line:
                license_key = line.split('=')[-1].strip()
            elif "http-referrer" in line:
                referrer = line.split('=')[-1].strip()
            elif "http-user-agent" in line:
                user_agent = line.split('=')[-1].strip()
            elif line.startswith("#EXTINF"):
                id_match = re.search(r'tvg-id="([^"]+)"', line)
                if id_match: tvg_id = id_match.group(1)
                
                name_match = re.search(r'tvg-name="([^"]*)"', line)
                if name_match: tvg_name = name_match.group(1)
                
                logo_match = re.search(r'tvg-logo="([^"]+)"', line)
                if logo_match: tvg_logo = logo_match.group(1)
                
                group_match = re.search(r'group-title="([^"]+)"', line)
                if group_match: group_title = group_match.group(1)
                
                title = line.split(',')[-1].strip()
                if not tvg_name: 
                    tvg_name = title
                    
            elif line.startswith("http://") or line.startswith("https://"):
                urls.append(line)
                
        if not urls:
            continue
            
        if referrer:
            ref_parsed = urlparse(referrer)
            origin = f"{ref_parsed.scheme}://{ref_parsed.netloc}"
        else:
            prim_parsed = urlparse(urls[0])
            referrer = f"{prim_parsed.scheme}://{prim_parsed.netloc}/"
            origin = f"{prim_parsed.scheme}://{prim_parsed.netloc}"

        print(f"Memeriksa Channel: {title}...")
        
        # Proses penyaringan URL yang AKTIF saja
        active_sources = []
        for url in urls:
            # Siapkan header sementara khusus untuk testing domain ini
            url_parsed = urlparse(url)
            test_headers = {
                "Referer": referrer if url == urls[0] else f"{url_parsed.scheme}://{url_parsed.netloc}/",
                "Origin": origin if url == urls[0] else f"{url_parsed.scheme}://{url_parsed.netloc}"
            }
            
            # Lakukan Validasi Ping HTTP
            if check_url_status(url, user_agent, test_headers):
                active_sources.append((url, test_headers))

        # Jika TIDAK ADA SATUPUN URL yang aktif dari channel ini, buang channel dari playlist
        if not active_sources:
            print(f" -> [DILEWATI] Channel '{title}' dihapus karena semua link mati.\n")
            continue

        # Susun ulang sources berdasarkan URL yang selamat/aktif
        sources_structure = []
        for idx, (url, hdrs) in enumerate(active_sources):
            is_primary = (idx == 0)
            drm_active = False
            current_key = ""
            current_type = ""
            
            # DRM Clearkey dilekatkan hanya jika URL pertama asal (indeks 0 teks) masih hidup dan membawa kunci
            if is_primary and license_key and url == urls[0]:
                drm_active = True
                current_key = license_key
                current_type = "clearkey" if "clearkey" in license_type.lower() else license_type

            sources_structure.append({
                "type": "primary" if is_primary else "backup",
                "uri": url,
                "headers": hdrs,
                "drm_info": {
                    "is_protected": drm_active,
                    "drm_type": current_type,
                    "drm_key": current_key
                }
            })

        temporary_channels.append({
            "title": title,
            "category": group_title,
            "sources": sources_structure,
            "user_agent": user_agent,
            "is_live": True,
            "match_id": "",
            "epg_metadata": {
                "tvg_id": tvg_id,
                "tvg_name": tvg_name,
                "tvg_logo": tvg_logo,
                "source_xml": "Embedded"
            }
        })
        print(f" -> [OK] {len(active_sources)} Link aktif dimasukkan.\n")
    
    # PROSES SORTING ALFABETIS A-Z
    temporary_channels.sort(key=lambda x: x["title"].lower())
    
    # PENOMORAN ID ULANG SECARA BERURUTAN
    playlist_json = []
    for index, channel in enumerate(temporary_channels, start=1):
        channel_ordered = {"id": index}
        channel_ordered.update(channel)
        playlist_json.append(channel_ordered)
        
    return playlist_json

# --- EKSEKUSI UTAMA (Gunakan ini jika sumber data berbentuk URL) ---

# GANTI DENGAN URL M3U ANDA
SUNDER_DATA_URL = "https://example.com" 

try:
    print(f"Mengunduh data mentah dari URL: {SUNDER_DATA_URL} ...")
    
    # Ambil data dari URL dengan timeout 10 detik
    headers_download = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"
    }
    response = requests.get(SUNDER_DATA_URL, headers=headers_download, timeout=10)
    
    if response.status_code == 200:
        m3u_content = response.text
        print("Unduhan berhasil! Memulai proses validasi...")
        
        print("\n--- MEMULAI PROSES PARSING & VALIDASI LIVE URL ---")
        hasil_json = parse_and_validate_m3u(m3u_content)

        # Simpan langsung ke file samaran Anda
        with open("system_config_v3.data", "w", encoding="utf-8") as f:
            json.dump(hasil_json, f, indent=4, ensure_ascii=False)

        print("--------------------------------------------------")
        print(f"SELESAI! Berhasil mengamankan {len(hasil_json)} Channel aktif ke 'system_config_v3.data'.\n")
    else:
        print(f"Gagal mengunduh data mentah. Server merespons dengan status: {response.status_code}")

except requests.RequestException as e:
    print(f"Gagal menyambung ke server sumber data. Error: {e}")

