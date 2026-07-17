import json
import re
from urllib.parse import urlparse
import requests

# URL SUMBER M3U DARI GITHUB BODYSLAM
SOURCE_URL = "https://raw.githubusercontent.com/uppermoon77/bodyslam/refs/heads/main/BS31AGUSTUS2026"
# OUTPUT FILE DI REPO NSTV
OUTPUT_FILE = ".system_config_v1.data"

# --- ATUR URUTAN KATEGORI DI SINI ---
CATEGORY_ORDER = ["NASIONAL", "FILM", "HBO"]

# DAFTAR KATA TERLARANG (Akan dibuang sepenuhnya)
BANNED_KEYWORDS = [
    "ORDER", "ORDER DISINI", "PESAN DI", "BELI", "W.A", "OLAHRAGA", "NEWS", "KIDS", "DOCUMENTARY", "HIBURAN", "DAERAH"
    "DUNIA INDIA NON SUB", "MAGELIFE INFORMATION", "MUSIC", "WORLD TV",
    "DUNIA TAIWAN ETC", "DUNIA SINGAPORE", "DUNIA JEPANG NON SUB", "DUNIA CHINA NON SUB",
    "DUNIA BRUNEI", "DUNIA MALAYSIA", "DUNIA AMERICA NON SUB", "DUNIA THAILAND ETC", "AGAMA"
]

def clean_channel_name(name):
    """Pembersihan nama dari emoji/simbol: '🆕⚽RCTI' -> 'RCTI'"""
    # Hapus semua karakter non-alfanumerik di awal/akhir
    clean = re.sub(r'^[^\w]+|[^\w]+$', '', name)
    # Hapus simbol di tengah
    clean = re.sub(r'[^\w\s]', '', clean)
    # Bersihkan spasi ganda
    clean = " ".join(clean.split())
    return clean.strip().upper()

def is_banned(text):
    """Mengecek apakah teks mengandung kata terlarang"""
    if not text: return False
    upper_text = text.upper()
    return any(keyword.upper() in upper_text for keyword in BANNED_KEYWORDS)

def get_tag_value(line, tag):
    """Fungsi pembantu untuk mengambil nilai di dalam tanda kutip (Aman)"""
    pattern = f'{tag}="([^"]*)"'
    match = re.search(pattern, line)
    return match.group(1) if match else ""

def check_url_status(url, user_agent, headers_dict):
    """Cek link aktif dengan GET Range 1 byte (Cepat & Akurat untuk Indosiar)"""
    custom_headers = {
        "User-Agent": user_agent,
        "Referer": headers_dict.get("Referer", ""),
        "Origin": headers_dict.get("Origin", ""),
        "Range": "bytes=0-0"
    }
    try:
        # Timeout 10 detik agar server Indosiar (tvratu) sempat merespon
        response = requests.get(url, headers=custom_headers, timeout=10, stream=True, allow_redirects=True)
        return response.status_code in [200, 206]
    except:
        return False

def run_automation():
    print(f"--- MENGAMBIL DATA SUMBER DARI GITHUB ---")
    try:
        response = requests.get(SOURCE_URL)
        if response.status_code != 200: 
            print(f"Gagal koneksi ke sumber: {response.status_code}")
            return
        input_text = response.text
    except Exception as e:
        print(f"Error: {e}")
        return

    # Pecah blok M3U berdasarkan tag #EXTINF (Menjamin metadata di atas URL tidak hilang)
    raw_blocks = re.split(r'#EXTINF', input_text)
    unique_channels = {}
    
    print(f"Memproses {len(raw_blocks)} blok data...")

    for block in raw_blocks:
        if not block.strip(): continue
        
        # Tambahkan kembali header yang hilang karena split
        full_block = "#EXTINF" + block
        lines = [l.strip() for l in full_block.split('\n') if l.strip()]
        
        # Inisialisasi metadata default
        ch_data = {
            "license_type": "org.w3.clearkey", # Format keinginan Master
            "license_key": "", "referrer": "",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "tvg_id": "", "tvg_logo": "", "group_title": "NASIONAL", "original_title": "", "urls": []
        }
        
        for line in lines:
            low_line = line.lower()
            # 1. Deteksi License Key (Support KODIPROP & Standar)
            if "license_key" in low_line:
                ch_data["license_key"] = line.split('=')[-1].strip()
            # 2. Deteksi License Type (Tetap pertahankan org.w3.clearkey)
            elif "license_type" in low_line:
                ch_data["license_type"] = line.split('=')[-1].strip()
            # 3. Deteksi User Agent (Krusial untuk Indosiar)
            elif "user-agent" in low_line:
                ch_data["user_agent"] = line.split('=')[-1].strip()
            # 4. Deteksi Referrer
            elif "referrer" in low_line:
                ch_data["referrer"] = line.split('=')[-1].strip()
            # 5. Metadata EXTINF
            elif line.startswith("#EXTINF"):
                ch_data["tvg_id"] = get_tag_value(line, "tvg-id")
                ch_data["tvg_logo"] = get_tag_value(line, "tvg-logo")
                ch_data["group_title"] = get_tag_value(line, "group-title") or "NASIONAL"
                ch_data["original_title"] = line.split(',')[-1].strip()
            # 6. Deteksi URL Streaming
            elif line.startswith("http"):
                ch_data["urls"].append(line)
        
        if not ch_data["urls"]: continue
        
        # SENSOR KONTEN "ORDER DISINI"
        if is_banned(ch_data["original_title"]) or is_banned(ch_data["group_title"]):
            continue

        clean_name = clean_channel_name(ch_data["original_title"])
        
        # Penentuan Header & Origin
        prim_url = ch_data["urls"][0]
        parsed_uri = urlparse(prim_url)
        if not ch_data["referrer"]:
            ch_data["referrer"] = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
        origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

        # VERIFIKASI LINK (PENTING: Gunakan User-Agent asli dari sumber)
        is_active = check_url_status(prim_url, ch_data["user_agent"], {"Referer": ch_data["referrer"], "Origin": origin})
        
        # Susun Payload DRM (org.w3.clearkey)
        drm_payload = {
            "is_protected": bool(ch_data["license_key"]),
            "drm_type": ch_data["license_type"],
            "drm_key": ch_data["license_key"]
        }

        # Susun List Sources (Fallback)
        sources_list = []
        for idx, u in enumerate(ch_data["urls"]):
            u_p = urlparse(u)
            sources_list.append({
                "type": "primary" if idx == 0 else "backup",
                "uri": u,
                "headers": {
                    "User-Agent": ch_data["user_agent"],
                    "Referer": ch_data["referrer"] if idx == 0 else f"{u_p.scheme}://{u_p.netloc}/",
                    "Origin": origin if idx == 0 else f"{u_p.scheme}://{u_p.netloc}"
                },
                "drm_info": drm_payload
            })

        # Hybrid Payload (Mendukung semua versi App agar pasti muncul)
        channel_payload = {
            "title": clean_name,
            "category": ch_data["group_title"].upper(),
            "uri": prim_url,
            "user_agent": ch_data["user_agent"],
            "headers": sources_list[0]["headers"],
            "drm_info": drm_payload,
            "sources": sources_list,
            "is_live": True,
            "is_active": is_active,
            "epg_metadata": {
                "tvg_id": ch_data["tvg_id"], 
                "tvg_name": clean_name, 
                "tvg_logo": ch_data["tvg_logo"], 
                "source_xml": "Embedded"
            }
        }

        # Logika Smart Replace: Utamakan link yang aktif untuk nama yang sama
        if clean_name in unique_channels:
            if not unique_channels[clean_name]["is_active"] and is_active:
                unique_channels[clean_name] = channel_payload
        else:
            unique_channels[clean_name] = channel_payload

    # Sorting berdasarkan prioritas kategori yang diatur Master
    all_channels = list(unique_channels.values())
    all_channels.sort(key=lambda x: (CATEGORY_ORDER.index(x["category"]) if x["category"] in CATEGORY_ORDER else len(CATEGORY_ORDER), x["title"]))

    # Penomoran ID ulang agar rapi
    final_playlist = []
    for idx, ch in enumerate(all_channels, start=1):
        if "is_active" in ch: del ch["is_active"]
        ordered = {"id": idx}
        ordered.update(ch)
        final_playlist.append(ordered)
        
    # Simpan ke file output (system_config_v3.data)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"channels": final_playlist}, f, indent=4, ensure_ascii=False)
    
    print(f"SELESAI! {len(final_playlist)} channel diproses. Indosiar UA: {ch_data['user_agent']}")

if __name__ == "__main__":
    run_automation()
