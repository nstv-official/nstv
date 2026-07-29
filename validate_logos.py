import json
import os
import re
import sys

def clean_name(text):
    """Membersihkan nama channel untuk pencocokan file logo."""
    if not text:
        return ""
    text = str(text).lower()
    # Hapus string spesifik (seperti v+) sebelum regex simbol
    text = text.replace('v+', '')
    text = re.sub(r'\b(hd|fhd|sd|4k|uhd|ag|indo|indonesia|tv)\b', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text

def get_sort_key(channel):
    name = channel.get('title', '')
    clean_start = re.sub(r'^[^\w]+', '', str(name))
    return clean_start.lower().strip()

def process_single_playlist(json_path, cleaned_logo_map, logos_folder):
    print(f"\n==========================================")
    print(f"📄 MEMPROSES BERKAS VIA FORCE V5: {json_path}")
    print(f"==========================================")
    
    if not os.path.exists(json_path):
        print(f"[⚠️ WARNING] File '{json_path}' tidak ditemukan. Dilewati.")
        return False

    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    try:
        playlist = json.loads(content)
    except json.JSONDecodeError:
        try:
            if not content.endswith(']'): playlist = json.loads(content + ']')
            elif not content.endswith('}'): playlist = json.loads(content + '}')
        except Exception as e:
            print(f"[❌ ERROR] JSON Tidak Bisa Diparse: {e}")
            return False

    # Deteksi struktur array
    if isinstance(playlist, list):
        raw_channels = playlist
        root_key = None
    elif isinstance(playlist, dict):
        root_key = next((k for k, v in playlist.items() if isinstance(v, list)), None)
        if root_key:
            raw_channels = playlist[root_key]
        else:
            raw_channels = [playlist]
            root_key = "SINGLE_OBJECT"
    else:
        return False

    # Hapus Duplikat
    unique_channels = []
    seen_names = set()
    seen_urls = set()
    for ch in raw_channels:
        if not isinstance(ch, dict): continue
        name = str(ch.get('title', '')).strip()
        url = str(ch.get('uri', '')).strip()
        if (name and name in seen_names) or (url and url in seen_urls):
            continue
        if name: seen_names.add(name)
        if url: seen_urls.add(url)
        unique_channels.append(ch)

    # Proses Penggantian Logo Agresif
    for index, channel in enumerate(unique_channels):
        original_name = channel.get('title', f"Index_{index}")
        cleaned_channel_name = clean_name(original_name)
        
        if 'epg_metadata' not in channel or channel['epg_metadata'] is None:
            channel['epg_metadata'] = {}
            
        epg = channel['epg_metadata']
        
        # Tentukan file gambar target dari folder logos lokal
        if cleaned_channel_name and cleaned_channel_name in cleaned_logo_map:
            matched_file = cleaned_logo_map[cleaned_channel_name]
            expected_logo_path = f"{logos_folder}/{matched_file}"
        else:
            expected_logo_path = f"{logos_folder}/default.png"

        # FORCING: Langsung timpa nilai logo lama tanpa membandingkan terlebih dahulu
        epg['tvg_logo'] = expected_logo_path

    # Urutkan A-Z
    unique_channels.sort(key=get_sort_key)

    # Pasang ID Urut Baru
    for new_id, channel in enumerate(unique_channels, start=1):
        channel['id'] = str(new_id)

    # RE-WRITE FORCED: Selalu simpan paksa file ke disk virtual GitHub runner
    if root_key == "SINGLE_OBJECT":
        final_data = unique_channels
    elif root_key:
        playlist[root_key] = unique_channels
        final_data = playlist
    else:
        final_data = unique_channels
        
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
    
    print(f"💾 [FORCED WRITE SUCCESS] Berkas {json_path} berhasil ditulis ulang!")
    return True

def validate_and_update_all(playlist_files, logos_folder):
    if not os.path.exists(logos_folder):
        sys.exit(1)
        
    logo_files = os.listdir(logos_folder)
    cleaned_logo_map = {}
    for filename in logo_files:
        name_only, _ = os.path.splitext(filename)
        cleaned_logo_map[clean_name(name_only)] = filename

    for file_path in playlist_files:
        process_single_playlist(file_path, cleaned_logo_map, logos_folder)
    sys.exit(0)

if __name__ == "__main__":
    target_playlists = [
        "system_config_v3.data",
        ".system_parseconfig_v2.dt"
    ]
    validate_and_update_all(target_playlists, "logos")
