import os
import re
import sys

def clean_name(text):
    """Membersihkan nama channel untuk pencocokan file logo."""
    if not text:
        return ""
    text = str(text).lower()
    text = text.replace('v+', '')
    text = re.sub(r'\(|\)|\[|\]', '', text)
    text = re.sub(r'\b(hd|fhd|sd|4k|uhd|ag|indo|indonesia|tv)\b', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = re.sub(r'\s+', '', text)
    return text.strip()

def process_large_playlist(file_path, cleaned_logo_map, base_raw_url, logos_folder):
    print(f"\n⚡ Memproses File Raksasa: {file_path}")
    if not os.path.exists(file_path):
        return False

    # Membaca seluruh isi file sebagai teks mentah
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Regex untuk mencari blok channel berdasarkan polanya
    # Skrip akan memisahkan setiap objek { ... } yang memiliki properti title
    channel_blocks = re.split(r'\}\s*,\s*\{\s*"id"', content)
    
    if len(channel_blocks) <= 1:
        # Coba pola pemisah alternatif jika formatnya sedikit berbeda
        channel_blocks = content.split('},\n    {')

    print(f"📊 Menemukan {len(channel_blocks)} blok objek channel.")
    
    updated_content = content
    
    # Cari setiap kecocokan judul dan ganti logo secara langsung menggunakan manipulasi string teks
    # Ini 1000x lebih cepat daripada memuat JSON ke memori
    title_pattern = re.compile(r'"title"\s*:\s*"([^"]+)"')
    logo_pattern = re.compile(r'"tvg_logo"\s*:\s*"([^"]+)"')

    # Pemindaian cepat
    for block in channel_blocks:
        title_match = title_pattern.search(block)
        if title_match:
            original_title = title_match.group(1)
            cleaned_title = clean_name(original_title)
            
            # Tentukan jalur logo target
            if cleaned_title in cleaned_logo_map:
                matched_file = cleaned_logo_map[cleaned_title]
                expected_url = f"{base_raw_url}/{logos_folder}/{matched_file}"
            else:
                expected_url = f"{base_raw_url}/{logos_folder}/default.png"
            
            # Cari baris tvg_logo yang ada di dalam blok channel ini
            logo_match = logo_pattern.search(block)
            if logo_match:
                old_logo_line = logo_match.group(0)
                new_logo_line = f'"tvg_logo": "{expected_url}"'
                
                # Ganti langsung di dokumen teks utama jika berbeda
                if old_logo_line != new_logo_line:
                    updated_content = updated_content.replace(old_logo_line, new_logo_line, 1)

    # Tulis kembali file berukuran besar secara langsung ke disk
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
        
    print(f"💾 [SUKSES BERHASIL] File {file_path} berhasil ditulis ulang!")
    return True

def validate_and_update_all(playlist_files, logos_folder):
    if not os.path.exists(logos_folder):
        print(f"[❌ ERROR] Folder '{logos_folder}' tidak ditemukan.")
        sys.exit(1)
        
    github_repository = os.getenv('GITHUB_REPOSITORY', 'nstv-official/nstv')
    github_ref_name = os.getenv('GITHUB_REF_NAME', 'main')
    
    base_raw_url = f"https://githubusercontent.com{github_repository}/{github_ref_name}"
    print(f"🌍 URL Raw Induk: {base_raw_url}")

    logo_files = os.listdir(logos_folder)
    cleaned_logo_map = {}
    for filename in logo_files:
        name_only, _ = os.path.splitext(filename)
        cleaned_logo_map[clean_name(name_only)] = filename

    for file_path in playlist_files:
        process_large_playlist(file_path, cleaned_logo_map, base_raw_url, logos_folder)
    sys.exit(0)

if __name__ == "__main__":
    target_playlists = [
        "system_config_v3.data",
        ".system_parseconfig_v2.dt"
    ]
    validate_and_update_all(target_playlists, "logos")
