import json
import os
import re
import sys

def clean_name(text):
    """Membersihkan nama channel untuk pencocokan logo."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r'\b(hd|fhd|sd|4k|uhd|ag|indo|indonesia|tv)\b', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text

def get_sort_key(channel):
    """Mengambil kunci pengurutan dengan membersihkan emoji di awal nama channel."""
    name = channel.get('name', '')
    clean_start = re.sub(r'^[^\w]+', '', name)
    return clean_start.lower().strip()

def validate_and_update_playlist(json_path, logos_folder):
    print("--- Memulai Validasi, Pembersihan Duplikat, Pengurutan & Penomoran ID ---")
    
    if not os.path.exists(logos_folder):
        print(f"[❌ ERROR] Folder '{logos_folder}' tidak ditemukan.")
        sys.exit(1)
        
    if not os.path.exists(os.path.join(logos_folder, "default.png")):
        print(f"[❌ ERROR] File 'default.png' wajib ada di folder '{logos_folder}'.")
        sys.exit(1)

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            playlist = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[❌ ERROR] Format JSON rusak: {e}")
        sys.exit(1)

    is_direct_list = isinstance(playlist, list)
    raw_channels = playlist if is_direct_list else playlist.get('channels', [])

    logo_files = os.listdir(logos_folder)
    cleaned_logo_map = {}
    for filename in logo_files:
        name_only, _ = os.path.splitext(filename)
        cleaned_logo_map[clean_name(name_only)] = filename

    # 1. Hapus Duplikasi (Berdasarkan Nama & URL Streaming)
    unique_channels = []
    seen_names = set()
    seen_urls = set()
    duplicate_count = 0

    for ch in raw_channels:
        name = ch.get('name', '').strip()
        url = ch.get('url', '').strip() # Ganti 'url' sesuai properti link streaming Anda

        if name in seen_names or (url and url in seen_urls):
            print(f"[🗑️ DUPLICATE] Menghapus channel duplikat: '{name}'")
            duplicate_count += 1
            continue
        
        seen_names.add(name)
        if url:
            seen_urls.add(url)
        unique_channels.append(ch)

    matched_count = 0
    updated_count = 0
    is_modified = duplicate_count > 0

    # 2. Validasi dan Perbarui Properti Logo
    for index, channel in enumerate(unique_channels):
        original_name = channel.get('name', f"Channel_Indeks_{index}")
        current_logo = channel.get('logo', '')
        cleaned_channel_name = clean_name(original_name)
        
        if cleaned_channel_name and cleaned_channel_name in cleaned_logo_map:
            matched_file = cleaned_logo_map[cleaned_channel_name]
            expected_logo_path = f"{logos_folder}/{matched_file}"
            if current_logo != expected_logo_path:
                channel['logo'] = expected_logo_path
                is_modified = True
            matched_count += 1
        else:
            default_path = f"{logos_folder}/default.png"
            if current_logo != default_path:
                channel['logo'] = default_path
                is_modified = True
                print(f"[✏️ UPDATED LOGO] '{original_name}' -> Menggunakan default.png")
            updated_count += 1

    # 3. Urutkan Secara Alfabetis (A-Z)
    print("🔀 Mengurutkan daftar channel dari A sampai Z...")
    before_sort = json.dumps(unique_channels, sort_keys=True)
    unique_channels.sort(key=get_sort_key)
    after_sort = json.dumps(unique_channels, sort_keys=True)
    
    if before_sort != after_sort:
        is_modified = True

    # 4. Pembaruan / Penomoran Ulang ID Otomatis
    print("🔢 Memperbarui urutan nomor ID channel...")
    for new_id, channel in enumerate(unique_channels, start=1):
        current_id = channel.get('id')
        
        # SESUAIKAN tipe data ID di sini. Contoh ini mengubah ID menjadi string ("1", "2", dll.)
        # Jika ID Anda berbentuk angka tanpa kutip, ubah str(new_id) menjadi cukup new_id
        expected_id = str(new_id) 
        
        if current_id != expected_id:
            channel['id'] = expected_id
            is_modified = True

    # 5. Simpan Perubahan ke Berkas JSON
    if is_modified:
        final_data = unique_channels if is_direct_list else {"channels": unique_channels}
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(final_data, f, indent=4, ensure_ascii=False)
        print(f"\n💾 Berhasil memperbarui, membersihkan duplikat, menyortir, dan menomori ulang berkas {json_path}!")
    else:
        print("\n✨ Tidak ada perubahan struktural, logo, duplikat, atau ID yang perlu disimpan.")

    print("\n=== LAPORAN AKHIR ===")
    print(f" Total Channel Awal     : {len(raw_channels)}")
    print(f" Duplikat Dihapus       : {duplicate_count}")
    print(f" Channel Aktif Saat Ini : {len(unique_channels)}")
    print(f" Logo Sesuai / Cocok    : {matched_count}")
    print(f" Menggunakan Default    : {updated_count}")
    print("=========================")
    sys.exit(0)

if __name__ == "__main__":
    validate_and_update_playlist("playlist.json", "logos")
