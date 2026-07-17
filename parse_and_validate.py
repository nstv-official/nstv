import json
import re
from urllib.parse import urlparse
import requests

SOURCE_URL = "https://raw.githubusercontent.com/uppermoon77/bodyslam/refs/heads/main/BS31AGUSTUS2026"
OUTPUT_FILE = "system_config_v3.data"

# URUTAN KATEGORI
CATEGORY_ORDER = ["NASIONAL", "OLAHRAGA", "HBO", "FILM", "KIDS", "NEWS", "DOCUMENTARY", "HIBURAN", "DAERAH"]

# DAFTAR KATA TERLARANG (Sangat Aman)
BANNED_KEYWORDS = [
    "ORDER", "ORDER DISINI", "PESAN DI", "BELI", "W.A",
    "INDIA NON SUB", "MAGELIFE INFORMATION", "MUSIC", "WORLD TV",
    "TAIWAN ETC", "SINGAPORE", "JEPANG NON SUB", "CHINA NON SUB",
    "BRUNEI", "MALAYSIA", "AMERICA NON SUB"
]

def clean_channel_name(name):
    """Pembersihan nama super teliti"""
    # Hapus semua karakter non-alfanumerik di awal/akhir
    clean = re.sub(r'^[^\w]+|[^\w]+$', '', name)
    # Hapus simbol di tengah
    clean = re.sub(r'[^\w\s]', '', clean)
    # Bersihkan spasi ganda
    clean = " ".join(clean.split())
    return clean.strip().upper()

def is_banned(text):
    if not text: return False
    upper_text = text.upper()
    return any(keyword.upper() in upper_text for keyword in BANNED_KEYWORDS)

def get_tag_value(line, tag):
    pattern = f'{tag}="([^"]*)"'
    match = re.search(pattern, line)
    return match.group(1) if match else ""

def check_url_status(url, user_agent, headers_dict):
    custom_headers = {
        "User-Agent": user_agent,
        "Referer": headers_dict.get("Referer", ""),
        "Origin": headers_dict.get("Origin", ""),
        "Range": "bytes=0-0"
    }
    try:
        response = requests.get(url, headers=custom_headers, timeout=10, stream=True, allow_redirects=True)
        return response.status_code in [200, 206]
    except:
        return False

def run_automation():
    print(f"--- MEMULAI PARSING ULTA TELITI ---")
    try:
        response = requests.get(SOURCE_URL)
        if response.status_code != 200: return
        input_text = response.text
    except: return

    # Split berdasarkan #EXTINF agar blok metadata di atas URL tidak hilang
    raw_blocks = re.split(r'#EXTINF', input_text)
    unique_channels = {}
    
    for block in raw_blocks:
        if not block.strip(): continue
        
        full_block = "#EXTINF" + block
        lines = [l.strip() for l in full_block.split('\n') if l.strip()]
        
        ch_data = {
            "license_type": "", "license_key": "", "referrer": "",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "tvg_id": "", "tvg_logo": "", "group_title": "NASIONAL", "original_title": "", "urls": []
        }
        
        for line in lines:
            low_line = line.lower()
            if "license_key" in low_line:
                ch_data["license_key"] = line.split('=')[-1].strip()
            elif "license_type" in low_line:
                ch_data["license_type"] = line.split('=')[-1].replace("org.w3.", "").strip()
            elif "user-agent" in low_line:
                ch_data["user_agent"] = line.split('=')[-1].strip()
            elif "referrer" in low_line:
                ch_data["referrer"] = line.split('=')[-1].strip()
            elif line.startswith("#EXTINF"):
                ch_data["tvg_id"] = get_tag_value(line, "tvg-id")
                ch_data["tvg_logo"] = get_tag_value(line, "tvg-logo")
                ch_data["group_title"] = get_tag_value(line, "group-title") or "NASIONAL"
                ch_data["original_title"] = line.split(',')[-1].strip()
            elif line.startswith("http"):
                ch_data["urls"].append(line)
        
        if not ch_data["urls"]: continue
        
        # SENSOR KONTEN TAK DIINGINKAN
        if is_banned(ch_data["original_title"]) or is_banned(ch_data["group_title"]):
            print(f" [BANNED] Melewati: {ch_data['original_title']}")
            continue

        clean_name = clean_channel_name(ch_data["original_title"])
        prim_url = ch_data["urls"][0]
        parsed_uri = urlparse(prim_url)
        if not ch_data["referrer"]:
            ch_data["referrer"] = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
        origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

        # VERIFIKASI LINK (PAKAI USER AGENT ASLI)
        is_active = check_url_status(prim_url, ch_data["user_agent"], {"Referer": ch_data["referrer"], "Origin": origin})
        
        drm_payload = {
            "is_protected": bool(ch_data["license_key"]),
            "drm_type": "clearkey" if "clearkey" in ch_data["license_type"].lower() else ch_data["license_type"],
            "drm_key": ch_data["license_key"]
        }

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
            "epg_metadata": {"tvg_id": ch_data["tvg_id"], "tvg_name": clean_name, "tvg_logo": ch_data["tvg_logo"], "source_xml": "Embedded"}
        }

        if clean_name in unique_channels:
            if not unique_channels[clean_name]["is_active"] and is_active:
                unique_channels[clean_name] = channel_payload
        else:
            unique_channels[clean_name] = channel_payload

    all_channels = list(unique_channels.values())
    all_channels.sort(key=lambda x: (CATEGORY_ORDER.index(x["category"]) if x["category"] in CATEGORY_ORDER else len(CATEGORY_ORDER), x["title"]))

    final_playlist = []
    for idx, ch in enumerate(all_channels, start=1):
        if "is_active" in ch: del ch["is_active"]
        ordered = {"id": idx}; ordered.update(ch)
        final_playlist.append(ordered)
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"channels": final_playlist}, f, indent=4, ensure_ascii=False)
    print(f"SUKSES! {len(final_playlist)} channel disimpan.")

if __name__ == "__main__":
    run_automation()
