import json
import os
import re
import sys

def clean_name(text):
    """Membersihkan nama channel untuk pencocokan file logo agar sangat toleran."""
    if not text:
        return ""
    text = str(text).lower()
    
    # Hapus string spesifik (seperti v+) sebelum menghapus simbol
    text = text.replace('v+', '')
    
    # Hapus tanda kurung, spasi, dan teks tambahan yang sering merusak kecocokan
    text = re.sub(r'\(|\)|\[|\]', '', text)
    text = re.sub(r'\b(hd|fhd|sd|4k|uhd|ag|indo|indonesia|tv)\b', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text.strip()

def get_sort_key(channel):
    name = channel.get('title', '')
    clean_start = re.sub(r'^[^\w]+', '', str(name))
    return clean_start.lower().strip()

def process_single_playlist(json_path, cleaned_logo_map, logos_folder, base_raw_url):
    print(f"\n==========================================")
    print(f"📄 MEMPROSES PLAYLIST DAN GENERATE URL RAW: {json_path}")
    print(f"==========================================")
    
    if not os.path.exists(json_path):
        print(f"[⚠️ WARNING] Berkas {json_path} tidak ditemukan.")
        return False

    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    try:
        playlist = json.loads(content)
    except json.JSONDecodeError as e:
        print(f"[❌ ERROR] JSON Tidak Bisa Diparse: {e}")
        return False

    if isinstance(playlist, list):
        raw_channels = playlist
        root_key = None
    elif isinstance(playlist, dict):
        root_key = next((k for k, v in playlist.items() if isinstance(v, list)), None)
        raw_channels = playlist[root_key] if root_key else [playlist]

    # 1. Hapus Duplikat Mandiri
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

    # 2. Proses Penggantian Logo menggunakan Format URL Raw Internet Terbuka
    for index, channel in enumerate(unique_channels):
        original_name = channel.get('title', f"Index_{index}")
        cleaned_channel_name = clean_name(original_name)
        
        if 'epg_metadata' not in channel or channel['epg_metadata'] is None:
            channel['epg_metadata'] = {}
            
        epg = channel['epg_metadata']
        
        # Cari kecocokan file gambar di map folder logos
        if cleaned_channel_name and cleaned_channel_name in cleaned_logo_map:
            matched_file = cleaned_logo_map[cleaned_channel_name]
            expected_logo_path = f"{base_raw_url}/{logos_folder}/{matched_file}"
            print(f"  [✅ COCOK] '{original_name}' -> Terhubung ke: {expected_logo_path}")
        else:
            expected_logo_path = f"{base_raw_url}/{logos_folder}/default.png"
            print(f"  [⚠️ DEFAULT] '{original_name}' (Bersih: '{cleaned_channel_name}') tidak ada di folder -> default.png")

        # Tulis ulang nilai objek epg_metadata secara absolut
        epg['tvg_logo'] = expected_logo_path

    # 3. Urutkan A-Z
    unique_channels.sort(key=get_sort_key)

    # 4. Pasang ID Urut Baru berbentuk Teks String ("1", "2", dll.)
    for new_id, channel in enumerate(unique_channels, start=1):
        channel['id'] = str(new_id)

    # 5. Simpan Kembali Hasil Akhir ke Berkas Fisik
    if root_key:
        playlist[root_key] = unique_channels
        final_data = playlist
    else:
        final_data = unique_channels
        
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(final_data, f, indent=4, ensure_ascii=False)
    
    print(f"💾 [BERHASIL] Berkas {json_path} sukses diperbarui dengan URL Raw GitHub Content!")
    return True

def validate_and_update_all(playlist_files, logos_folder):
    if not os.path.exists(logos_folder):
        print(f"[❌ ERROR] Folder '{logos_folder}' tidak ditemukan.")
        sys.exit(1)
        
    # Ambil data lingkungan dari sistem repositori GitHub Anda
    github_repository = os.getenv('GITHUB_REPOSITORY', 'USER/REPO')
    github_ref_name = os.getenv('GITHUB_REF_NAME', 'main')
    
    # FORMAT PENULISAN URL RAW TRADISIONAL (Mendukung semua jenis Media Player)
    base_raw_url = f"https://raw.githubusercontent.com/{github_repository}/{github_ref_name}"
    print(f"🌍 Base URL Raw Terkonfigurasi: {base_raw_url}")

    logo_files = os.listdir(logos_folder)
    cleaned_logo_map = {}
    for filename in logo_files:
        name_only, _ = os.path.splitext(filename)
        cleaned_logo_map[clean_name(name_only)] = filename

    for file_path in playlist_files:
        process_single_playlist(file_path, cleaned_logo_map, logos_folder, base_raw_url)
    sys.exit(0)

if __name__ == "__main__":
    target_playlists = [
        "system_config_v3.data",
        ".system_parseconfig_v2.dt"
    ]
    validate_and_update_all(target_playlists, "logos")
