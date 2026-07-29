import json
import os
import re
import sys

def clean_name(text):
    """Membersihkan nama channel untuk pencocokan file logo."""
    if not text:
        return ""
    text = text.lower()
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
    print(f"📄 MEMPROSES BERKAS: {json_path}")
    print(f"==========================================")
    
    if not os.path.exists(json_path):
        print(f"[⚠️ WARNING] File '{json_path}' tidak ditemukan. Dilewati.")
        return False

    # 1. Baca isi file
    with open(json_path, 'r', encoding='utf-8') as f:
        content = f.read().strip()

    # Perbaikan Autodeteksi Struktur JSON yang Berantakan/Dibungkus
    try:
        playlist = json.loads(content)
    except json.JSONDecodeError:
        # Jika gagal load, coba bersihkan karakter pembungkus jika file tidak lengkap
        try:
            if not content.endswith(']'):
                playlist = json.loads(content + ']')
            elif not content.endswith('}'):
                playlist = json.loads(content + '}')
        except Exception as e:
            print(f"[❌ ERROR] JSON Rusak Parah & Tidak Bisa Diparse: {e}")
            return False

    # Cari array channel di posisi mana pun di dalam dokumen JSON
    raw_channels = []
    root_key = None
    
    if isinstance(playlist, list):
        raw_channels = playlist
    elif isinstance(playlist, dict):
        if 'channels' in playlist and isinstance(playlist['channels'], list):
            raw_channels = playlist['channels']
            root_key = 'channels'
        else:
            # Cari kunci acak pertama yang isinya berupa List/Array
            for k, v in playlist.items():
                if isinstance(v, list):
                    raw_channels = v
                    root_key = k
                    break
            # Jika tidak ada list di dalam objek, bungkus objek tunggal tersebut menjadi list
            if not raw_channels:
                raw_channels = [playlist]
                root_key = "SINGLE_OBJECT"

    if not raw_channels:
        print(f"[❌ ERROR] Gagal mengekstrak daftar channel dari JSON.")
        return False

    print(f"📊 Menemukan {len(raw_channels)} data channel untuk diproses.")

    # 2. Pembersihan Duplikat Terisolasi
    unique_channels = []
    seen_names = set()
    seen_urls = set()
    duplicate_count = 0

    for ch in raw_channels:
        if not isinstance(ch, dict): continue
        name = str(ch.get('title', '')).strip()
        url = str(ch.get('uri', '')).strip()

        if (name and name in seen_names) or (url and url in seen_urls):
            duplicate_count += 1
            continue
        
        if name: seen_names.add(name)
        if url: seen_urls.add(url)
        unique_channels.append(ch)

    is_modified = duplicate_count > 0
    matched_count = 0
    updated_count = 0

    # 3. Proses Ganti Tautan Logo EPG
    for index, channel in enumerate(unique_channels):
        original_name = channel.get('title', f"Index_{index}")
        cleaned_channel_name = clean_name(original_name)
        
        if 'epg_metadata' not in channel or channel['epg_metadata'] is None:
            channel['epg_metadata'] = {}
            is_modified = True
            
        epg = channel['epg_metadata']
        current_logo = epg.get('tvg_logo', '')
        
        # Tentukan logo berdasarkan kecocokan di folder logos/
        if cleaned_channel_name and cleaned_channel_name in cleaned_logo_map:
            matched_file = cleaned_logo_map[cleaned_channel_name]
            expected_logo_path = f"{logos_folder}/{matched_file}"
            matched_count += 1
        else:
            expected_logo_path = f"{logos_folder}/default.png"
            updated_count += 1

        if current_logo != expected_logo_path:
            epg['tvg_logo'] = expected_logo_path
            is_modified = True
            print(f"✏️ [MENGUBAH MEMORI] '{original_name}' -> {expected_logo_path}")

    # 4. Urutkan Alfabetis A-Z
    unique_channels.sort(key=get_sort_key)

    # 5. Pasang ID Urut Baru
    for new_id, channel in enumerate(unique_channels, start=1):
        current_id = channel.get('id')
        expected_id = new_id if isinstance(current_id, int) else str(new_id)
        if current_id != expected_id:
            channel['id'] = expected_id
            is_modified = True

    # 6. Tulis Kembali Hasil Akhir Secara Utuh ke Disk Virtual
    if is_modified:
        if root_key == "SINGLE_OBJECT":
            final_data = unique_channels[0]
        elif root_key:
            playlist[root_key] = unique_channels
            final_data = playlist
        else:
            final_data = unique_channels
            
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"💾 [SUKSES DISIMPAN] Berkas {json_path} berhasil diperbarui secara fisik!")
    else:
        print("✨ [SAMA] Tidak ada perubahan terdeteksi pada logo maupun urutan.")

    return True

def validate_and_update_all(playlist_files, logos_folder):
    print("--- Memulai Validasi Multi-Playlist Paket Lengkap (V4) ---")
    if not os.path.exists(logos_folder):
        print(f"[❌ ERROR] Folder '{logos_folder}' tidak ditemukan.")
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
