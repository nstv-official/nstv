import json
import os
import re
import sys

def clean_name(text):
    """Membersihkan nama channel untuk pencocokan file logo."""
    if not text:
        return ""
    text = text.lower()
    # Menghapus variasi teks tambahan, spasi, dan simbol
    text = re.sub(r'\b(hd|fhd|sd|4k|uhd|ag|indo|indonesia|tv|v\+)\b', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text

def get_sort_key(channel):
    """Mengambil kunci pengurutan berdasarkan properti 'title'."""
    name = channel.get('title', '')
    clean_start = re.sub(r'^[^\w]+', '', str(name))
    return clean_start.lower().strip()

def process_single_playlist(json_path, cleaned_logo_map, logos_folder):
    print(f"\n📄 Memproses File: {json_path}")
    
    if not os.path.exists(json_path):
        print(f"[⚠️ WARNING] File '{json_path}' tidak ditemukan. Dilewati.")
        return False

    # 1. Baca isi file JSON playlist
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            playlist = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[❌ ERROR] Format JSON pada file {json_path} rusak: {e}")
        return False

    is_direct_list = isinstance(playlist, list)
    raw_channels = playlist if is_direct_list else playlist.get('channels', [])

    # 2. HAPUS DUPLIKASI (Terisolasi per file, cek berdasarkan 'title' dan 'uri')
    unique_channels = []
    seen_names = set()
    seen_urls = set()
    duplicate_count = 0

    for ch in raw_channels:
        name = str(ch.get('title', '')).strip()
        url = str(ch.get('uri', '')).strip()

        if not name and not url:
            continue

        if (name and name in seen_names) or (url and url in seen_urls):
            print(f"  [🗑️ DUPLICATE] Menghapus duplikat di file ini: '{name}'")
            duplicate_count += 1
            continue
        
        if name:
            seen_names.add(name)
        if url:
            seen_urls.add(url)
            
        unique_channels.append(ch)

    matched_count = 0
    updated_count = 0
    is_modified = duplicate_count > 0

    # 3. Validasi dan Perbarui Properti Logo di dalam 'epg_metadata'
    for index, channel in enumerate(unique_channels):
        original_name = channel.get('title', f"Channel_Indeks_{index}")
        cleaned_channel_name = clean_name(original_name)
        
        # Pastikan objek 'epg_metadata' ada di dalam data channel
        if 'epg_metadata' not in channel or channel['epg_metadata'] is None:
            channel['epg_metadata'] = {}
            is_modified = True
            
        epg = channel['epg_metadata']
        current_logo = epg.get('tvg_logo', '')
        
        # Tentukan jalur logo baru yang diharapkan
        if cleaned_channel_name and cleaned_channel_name in cleaned_logo_map:
            matched_file = cleaned_logo_map[cleaned_channel_name]
            expected_logo_path = f"{logos_folder}/{matched_file}"
            matched_count += 1
        else:
            expected_logo_path = f"{logos_folder}/default.png"
            updated_count += 1

        # Jika logo saat ini berbeda dengan logo baru/default, lakukan pembaruan
        if current_logo != expected_logo_path:
            epg['tvg_logo'] = expected_logo_path
            is_modified = True
            print(f"  [✏️ UPDATED LOGO] '{original_name}' -> Diubah ke: {expected_logo_path}")

    # 4. Urutkan Secara Alfabetis (A-Z) berdasarkan 'title'
    print("  🔀 Mengurutkan daftar channel dari A sampai Z...")
    before_sort = json.dumps(unique_channels, sort_keys=True)
    unique_channels.sort(key=get_sort_key)
    after_sort = json.dumps(unique_channels, sort_keys=True)
    
    if before_sort != after_sort:
        is_modified = True

    # 5. Pembaruan / Penomoran Ulang ID Otomatis
    print("  🔢 Memperbarui urutan nomor ID channel...")
    for new_id, channel in enumerate(unique_channels, start=1):
        current_id = channel.get('id')
        
        # Jika tipe data ID asli berupa integer/angka, pertahankan integer
        if isinstance(current_id, int):
            expected_id = new_id
        else:
            expected_id = str(new_id)
        
        if current_id != expected_id:
            channel['id'] = expected_id
            is_modified = True

    # 6. Simpan Perubahan ke Berkas jika modifikasi terjadi
    if is_modified:
        final_data = unique_channels if is_direct_list else {"channels": unique_channels}
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"  💾 Berhasil memperbarui berkas {json_path}!")
    else:
        print("  ✨ Tidak ada perubahan struktural yang perlu disimpan.")

    print(f"  --- Ringkasan {json_path} ---")
    print(f"  Total Channel Awal     : {len(raw_channels)}")
    print(f"  Duplikat Dihapus       : {duplicate_count}")
    print(f"  Channel Aktif Saat Ini : {len(unique_channels)}")
    print(f"  Logo Berhasil Cocok    : {matched_count}")
    print(f"  Menggunakan Default    : {updated_count}")
    return True

def validate_and_update_all(playlist_files, logos_folder):
    print("--- Memulai Validasi Multi-Playlist Terisolasi (Skema Objek EPG) ---")
    
    if not os.path.exists(logos_folder):
        print(f"[❌ ERROR] Folder '{logos_folder}' tidak ditemukan.")
        sys.exit(1)
        
    if not os.path.exists(os.path.join(logos_folder, "default.png")):
        print(f"[❌ ERROR] File 'default.png' wajib ada di folder '{logos_folder}'.")
        sys.exit(1)

    logo_files = os.listdir(logos_folder)
    cleaned_logo_map = {}
    for filename in logo_files:
        name_only, _ = os.path.splitext(filename)
        cleaned_logo_map[clean_name(name_only)] = filename

    for file_path in playlist_files:
        process_single_playlist(file_path, cleaned_logo_map, logos_folder)
        
    print("\n🎉 Semua file playlist selesai diproses!")
    sys.exit(0)

if __name__ == "__main__":
    target_playlists = [
        "system_config_v3.data",
        ".system_parseconfig_v2.dt"
    ]
    validate_and_update_all(target_playlists, "logos")
