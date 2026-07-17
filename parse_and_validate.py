import json
import re
from urllib.parse import urlparse
import requests

# URL SUMBER M3U DARI GITHUB BODYSLAM
SOURCE_URL = "https://raw.githubusercontent.com/uppermoon77/bodyslam/refs/heads/main/BS31AGUSTUS2026"
# OUTPUT FILE DI REPO NSTV
OUTPUT_FILE = "system_config_v3.data"

# --- ATUR URUTAN KATEGORI DI SINI ---
CATEGORY_ORDER = [
    "NASIONAL",
    "FILM",
    "HBO",
    "KIDS",
    "DAERAH"
    "HIBURAN",
    "NEWS",
    "DOCUMENTARY",
    "OLAHRAGA",
]

# Kata kunci yang dilarang (Akan dibuang sepenuhnya)
BANNED_KEYWORDS = ["ORDER", "ORDER DISINI", "PESAN DI", "BELI", "W.A"]

def clean_channel_name(name):
    """Membersihkan nama dari emoji/simbol"""
    clean = re.sub(r'[^\w\s]', '', name)
    clean = " ".join(clean.split())
    return clean.strip().upper()

def is_banned(text):
    """Mengecek apakah teks mengandung kata terlarang"""
    if not text: return False
    upper_text = text.upper()
    return any(keyword in upper_text for keyword in BANNED_KEYWORDS)

def get_tag_value(line, tag):
    """Ambil nilai tag (tvg-id, dll) secara aman"""
    pattern = f'{tag}="([^"]+)"'
    match = re.search(pattern, line)
    return match.group(1) if match else ""

def check_url_status(url, user_agent, headers_dict):
    """Cek link aktif dengan GET Range 1 byte"""
    custom_headers = {
        "User-Agent": user_agent,
        "Referer": headers_dict.get("Referer", ""),
        "Origin": headers_dict.get("Origin", ""),
        "Range": "bytes=0-0"
    }
    try:
        response = requests.get(url, headers=custom_headers, timeout=5, stream=True, allow_redirects=True)
        return response.status_code in [200, 206]
    except:
        return False

def run_automation():
    print(f"--- MENGAMBIL DATA SUMBER ---")
    try:
        response = requests.get(SOURCE_URL)
        if response.status_code != 200: return
        input_text = response.text
    except: return

    raw_blocks = re.split(r'\n\s*\+\s*\+\s*\+\s*\+\s*\n|\n\s*\n', input_text)
    unique_channels = {}
    
    for block in raw_blocks:
        block = block.strip()
        if not block or "#EXTINF" not in block: continue
            
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
                data["tvg_id"] = get_tag_value(line, "tvg-id")
                data["tvg_logo"] = get_tag_value(line, "tvg-logo")
                data["group_title"] = get_tag_value(line, "group-title") or "NASIONAL"
                data["original_title"] = line.split(',')[-1].strip()
            elif line.startswith("http"): data["urls"].append(line)
        
        if not data["urls"]: continue

        # SENSOR KATA TERLARANG
        if is_banned(data["original_title"]) or is_banned(data["group_title"]):
            continue

        clean_name = clean_channel_name(data["original_title"])
        prim_url = data["urls"][0]
        parsed_uri = urlparse(prim_url)
        if not data["referrer"]: data["referrer"] = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
        origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

        is_active = check_url_status(prim_url, data["user_agent"], {"Referer": data["referrer"], "Origin": origin})
        
        drm_payload = {
            "is_protected": bool(data["license_key"]),
            "drm_type": "clearkey" if "clearkey" in data["license_type"].lower() else data["license_type"],
            "drm_key": data["license_key"]
        }

        sources_list = []
        for idx, u in enumerate(data["urls"]):
            u_p = urlparse(u)
            sources_list.append({
                "type": "primary" if idx == 0 else "backup",
                "uri": u,
                "headers": {
                    "User-Agent": data["user_agent"],
                    "Referer": data["referrer"] if idx == 0 else f"{u_p.scheme}://{u_p.netloc}/",
                    "Origin": origin if idx == 0 else f"{u_p.scheme}://{u_p.netloc}"
                },
                "drm_info": drm_payload
            })

        # CHANNEL PAYLOAD DENGAN DUKUNGAN APLIKASI LAMA (Field uri/headers/drm_info di luar)
        channel_payload = {
            "title": clean_name,
            "category": data["group_title"].upper(),
            "uri": prim_url,  # <--- WAJIB UNTUK APLIKASI LAMA
            "user_agent": data["user_agent"],
            "headers": sources_list[0]["headers"], # <--- WAJIB UNTUK APLIKASI LAMA
            "drm_info": drm_payload, # <--- WAJIB UNTUK APLIKASI LAMA
            "sources": sources_list, # <--- UNTUK APLIKASI BARU
            "is_live": True,
            "is_active": is_active,
            "epg_metadata": {"tvg_id": data["tvg_id"], "tvg_name": clean_name, "tvg_logo": data["tvg_logo"], "source_xml": "Embedded"}
        }

        if clean_name in unique_channels:
            if not unique_channels[clean_name]["is_active"] and is_active:
                unique_channels[clean_name] = channel_payload
        else:
            unique_channels[clean_name] = channel_payload

    # SORTIR KATEGORI
    def get_category_priority(ch_item):
        cat = ch_item["category"]
        return CATEGORY_ORDER.index(cat) if cat in CATEGORY_ORDER else len(CATEGORY_ORDER)

    all_channels = list(unique_channels.values())
    all_channels.sort(key=lambda x: (get_category_priority(x), x["title"]))

    final_playlist = []
    for idx, ch_data in enumerate(all_channels, start=1):
        if "is_active" in ch_data: del ch_data["is_active"]
        ordered_entry = {"id": idx}
        ordered_entry.update(ch_data)
        final_playlist.append(ordered_entry)
        
    final_response = {"channels": final_playlist}
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final_response, f, indent=4, ensure_ascii=False)
    print(f"SELESAI! {len(final_playlist)} channel disimpan.")

if __name__ == "__main__":
    run_automation()
