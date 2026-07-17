import json
import re
from urllib.parse import urlparse
import requests

SOURCE_URL = "https://raw.githubusercontent.com/uppermoon77/bodyslam/refs/heads/main/BS31AGUSTUS2026"
OUTPUT_FILE = "system_config_v3.data"

CATEGORY_ORDER = ["NASIONAL", "OLAHRAGA", "NEWS", "FILM", "KIDS", "DOCUMENTARY", "HIBURAN", "DAERAH"]
BANNED_KEYWORDS = ["ORDER", "ORDER DISINI", "PESAN DI", "BELI", "W.A"]

def clean_channel_name(name):
    # Hapus emoji dan simbol (Termasuk kurung dan tanda centang)
    clean = re.sub(r'[^\w\s]', '', name)
    # Hapus kata '🆕' atau emoji lain yang tersisa
    clean = re.sub(r'[^\x00-\x7F]+', '', clean)
    clean = " ".join(clean.split())
    return clean.strip().upper()

def is_banned(text):
    if not text: return False
    upper_text = text.upper()
    return any(keyword in upper_text for keyword in BANNED_KEYWORDS)

def get_tag_value(line, tag):
    pattern = f'{tag}="([^"]*)"'
    match = re.search(pattern, line)
    return match.group(1) if match else ""

def check_url_status(url, user_agent, headers_dict):
    """Pengecekan super teliti dengan User-Agent yang sesuai sumber"""
    custom_headers = {
        "User-Agent": user_agent,
        "Referer": headers_dict.get("Referer", ""),
        "Origin": headers_dict.get("Origin", ""),
        "Range": "bytes=0-0"
    }
    try:
        # Timeout 7 detik karena server seperti tvratu terkadang butuh waktu handshake DRM
        response = requests.get(url, headers=custom_headers, timeout=7, stream=True, allow_redirects=True)
        return response.status_code in [200, 206]
    except:
        return False

def run_automation():
    print(f"--- MEMULAI PARSING SUPER TELITI ---")
    try:
        response = requests.get(SOURCE_URL)
        if response.status_code != 200: return
        input_text = response.text
    except: return

    # Pecah blok M3U dengan lebih fleksibel (mendukung berbagai pemisah)
    raw_blocks = re.split(r'#EXTINF', input_text)
    unique_channels = {}
    
    for block in raw_blocks:
        if not block.strip(): continue
        
        # Tambahkan kembali header yang hilang karena split
        full_block = "#EXTINF" + block
        lines = [l.strip() for l in full_block.split('\n') if l.strip()]
        
        # Inisialisasi metadata
        ch_data = {
            "license_type": "", "license_key": "", "referrer": "",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "tvg_id": "", "tvg_logo": "", "group_title": "NASIONAL", "original_title": "", "urls": []
        }
        
        for line in lines:
            # 1. Deteksi License Key (Support KODIPROP & Format standar)
            if "license_key" in line.lower():
                ch_data["license_key"] = line.split('=')[-1].strip()
            elif "license_type" in line.lower():
                ch_data["license_type"] = line.split('=')[-1].replace("org.w3.", "").strip()
            
            # 2. Deteksi User Agent (Support EXTVLCOPT & KODIPROP)
            elif "user-agent" in line.lower():
                ch_data["user_agent"] = line.split('=')[-1].strip()
            
            # 3. Deteksi Referrer
            elif "referrer" in line.lower():
                ch_data["referrer"] = line.split('=')[-1].strip()
                
            # 4. Deteksi Metadata EXTINF
            elif line.startswith("#EXTINF"):
                ch_data["tvg_id"] = get_tag_value(line, "tvg-id")
                ch_data["tvg_logo"] = get_tag_value(line, "tvg-logo")
                ch_data["group_title"] = get_tag_value(line, "group-title") or "NASIONAL"
                ch_data["original_title"] = line.split(',')[-1].strip()
            
            # 5. Deteksi URL
            elif line.startswith("http"):
                ch_data["urls"].append(line)
        
        if not ch_data["urls"] or is_banned(ch_data["original_title"]): continue

        clean_name = clean_channel_name(ch_data["original_title"])
        
        # Logika Headers & Origin
        prim_url = ch_data["urls"][0]
        parsed_uri = urlparse(prim_url)
        if not ch_data["referrer"]:
            ch_data["referrer"] = f"{parsed_uri.scheme}://{parsed_uri.netloc}/"
        origin = f"{parsed_uri.scheme}://{parsed_uri.netloc}"

        # VERIFIKASI LINK (PENTING: Pakai UA dari sumber!)
        headers_for_test = {"Referer": ch_data["referrer"], "Origin": origin}
        is_active = check_url_status(prim_url, ch_data["user_agent"], headers_for_test)
        
        # Build DRM Info
        drm_active = bool(ch_data["license_key"])
        drm_type = "clearkey" if "clearkey" in ch_data["license_type"].lower() else ch_data["license_type"]
        drm_payload = {"is_protected": drm_active, "drm_type": drm_type, "drm_key": ch_data["license_key"]}

        # Build Sources
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

        # Hybrid Payload (Support Semua Versi App)
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

        # Logika Replace/Add
        if clean_name in unique_channels:
            # Utamakan yang aktif
            if not unique_channels[clean_name]["is_active"] and is_active:
                unique_channels[clean_name] = channel_payload
        else:
            unique_channels[clean_name] = channel_payload

    # Final Sort & ID
    all_channels = list(unique_channels.values())
    all_channels.sort(key=lambda x: (CATEGORY_ORDER.index(x["category"]) if x["category"] in CATEGORY_ORDER else len(CATEGORY_ORDER), x["title"]))

    final_playlist = []
    for idx, ch in enumerate(all_channels, start=1):
        if "is_active" in ch: del ch["is_active"]
        ordered = {"id": idx}; ordered.update(ch)
        final_playlist.append(ordered)
        
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"channels": final_playlist}, f, indent=4, ensure_ascii=False)
    print(f"SELESAI! {len(final_playlist)} channel diproses dengan UA khusus.")

if __name__ == "__main__":
    run_automation()
