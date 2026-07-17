import json
import re
from urllib.parse import urlparse
import requests

# URL SUMBER M3U DARI GITHUB BODYSLAM
SOURCE_URL = "https://raw.githubusercontent.com/uppermoon77/bodyslam/refs/heads/main/BS31AGUSTUS2026"
# OUTPUT FILE DI REPO NSTV
OUTPUT_FILE = "system_config_v3.data"

def clean_channel_name(name):
    """
    Membersihkan nama dari emoji, simbol, dan karakter spesial.
    Contoh: '🆕⚽✅RCTI ✅' -> 'RCTI'
    """
    # 1. Hapus karakter non-alfanumerik (termasuk emoji) tapi sisakan spasi dan angka
    clean = re.sub(r'[^\w\s]', '', name)
    # 2. Hapus spasi berlebih dan ubah ke Uppercase
    clean = " ".join(clean.split())
    return clean.strip().upper()

def check_url_status(url, user_agent, headers_dict):
    """
    Cek link aktif dengan GET Range 1 byte (Sangat Cepat & Hemat Kuota)
    """
    custom_headers = {
        "User-Agent": user_agent,
        "Referer": headers_dict.get("Referer", ""),
        "Origin": headers_dict.get("Origin", ""),
        "Range": "bytes=0-0"
    }
    try:
        # Gunakan stream=True agar tidak mendownload konten video
        response = requests.get(url, headers=custom_headers, timeout=5, stream=True, allow_redirects=True)
        # Status 200 atau 206 (Partial Content) dianggap HIDUP
        return response.status_code in [200, 206]
    except:
        return False

def run_automation():
    print(f"--- MENGAMBIL DATA SUMBER DARI GITHUB ---")
    try:
        response = requests.get(SOURCE_URL)
        if response.status_code != 200:
            print(f"Gagal mengambil data. Status: {response.status_code}")
            return
        input_text = response.text
    except Exception as e:
        print(f"Error Koneksi: {e}")
        return

    # Pecah blok M3U berdasarkan baris kosong atau pemisah ++++
    raw_blocks = re.split(r'\n\s*\+\s*\+\s*\+\s*\+\s*\n|\n\s*\n', input_text)
    unique_channels = {}
    channel_order = []

    print(f"Memproses {len(raw_blocks)} blok data...")

    for block in raw_blocks:
        block = block.strip()
        if not block or "#EXTINF" not in block:
            continue
            
        lines = block.split('\n')
        data = {
            "license_type": "", "license_key": "", "referrer": "",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "tvg_id": "", "tvg_logo": "", "group_title": "NASIONAL", "original_title": "Unknown", "urls": []
        }
        
        for line in lines:
            line = line.strip()
            if not line: continue
            if "license_type" in line: data["license_type"] = line.split('=')[-1].replace("org.w3.", "").strip()
            elif "license_key" in line: data["license_key"] = line.split('=')[-1].strip()
            elif "http-referrer" in line: data["referrer"] = line.split('=')[-1].strip()
            elif "http-user-agent" in line: data["user_agent"] = line.split('=')[-1].strip()
            elif line.startswith("#EXTINF"):
                data["tvg_id"] = (re.search(r'tvg-id="([^"]+)"', line) or re.search(r'', '')).group(1) if 'tvg-id="' in line else ""
                data["tvg_logo"] = (re.search(r'tvg-logo="([^"]+)"', line) or re.search(r'', '')).group(1) if 'tvg-logo="' in line else ""
                data["group_title"] = (re.search(r'group-title="([^"]+)"', line) or re.search(r'', '')).group(1) if 'group-title="' in line else "NASIONAL"
                data["original_title"] = line.split(',')[-1].strip()
            elif line.startswith("http"):
                data["urls"].append(line)
        
        if not data["urls"]: continue

        # --- LOGIKA SMART NAME & MERGE ---
        clean_name = clean_channel_name(data["original_title"])
        
        # Penentuan Header Dasar
        prim_url = data["urls"][0]
        parsed_uri = urlparse(prim_url)
        if not data["referrer"]:
            data["referrer"] = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
        origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

        # Validasi Keaktifan Link Utama
        test_headers = {"Referer": data["referrer"], "Origin": origin}
        is_active = check_url_status(prim_url, data["user_agent"], test_headers)
        
        # Susun Metadata DRM
        drm_payload = {
            "is_protected": True if data["license_key"] else False,
            "drm_type": "clearkey" if "clearkey" in data["license_type"].lower() else data["license_type"],
            "drm_key": data["license_key"]
        }

        # Susun List Sources
        sources_list = []
        for idx, u in enumerate(data["urls"]):
            u_parsed = urlparse(u)
            sources_list.append({
                "type": "primary" if idx == 0 else "backup",
                "uri": u,
                "headers": {
                    "User-Agent": data["user_agent"],
                    "Referer": data["referrer"] if idx == 0 else f"{u_parsed.scheme}://{u_parsed.netloc}/",
                    "Origin": origin if idx == 0 else f"{u_parsed.scheme}://{u_parsed.netloc}"
                },
                "drm_info": drm_payload
            })

        channel_payload = {
            "title": clean_name,
            "category": data["group_title"],
            "sources": sources_list,
            "user_agent": data["user_agent"],
            "is_live": True,
            "is_active": is_active, # Untuk seleksi internal
            "epg_metadata": {
                "tvg_id": data["tvg_id"],
                "tvg_name": clean_name,
                "tvg_logo": data["tvg_logo"],
                "source_xml": "Embedded"
            }
        }

        # --- LOGIKA REPLACE JIKA AKTIF ---
        if clean_name in unique_channels:
            # Jika sudah ada, tapi yang lama mati dan yang baru ini aktif, TIMPA!
            if not unique_channels[clean_name]["is_active"] and is_active:
                unique_channels[clean_name] = channel_payload
        else:
            # Jika channel baru, tambahkan ke daftar dan catat urutannya
            unique_channels[clean_name] = channel_payload
            channel_order.append(clean_name)

    # --- PENYUSUNAN JSON AKHIR ---
    final_playlist = []
    for idx, name in enumerate(channel_order, start=1):
        ch_data = unique_channels[name]
        # Hapus flag internal agar JSON bersih
        if "is_active" in ch_data: del ch_data["is_active"]
        
        # Tambahkan ID berurutan
        ordered_entry = {"id": idx}
        ordered_entry.update(ch_data)
        final_playlist.append(ordered_entry)
        
    # Bungkus dalam format NSTV (Object dengan key "channels")
    final_response = {"channels": final_playlist}

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_response, f, indent=4, ensure_ascii=False)
    
    print(f"\nSELESAI! Berhasil mengupdate {OUTPUT_FILE} dengan {len(final_playlist)} channel.")

if __name__ == "__main__":
    run_automation()
