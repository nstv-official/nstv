import requests
import json
import concurrent.futures

# DAFTAR FILE YANG AKAN DIBERSIHKAN
FILES_TO_CLEAN = ["playlist.json", "voli.json", "futsal.json"]
TIMEOUT = 15

# Header agar tidak diblokir server (Menyamar jadi Browser)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
}

def check_link(item):
    # Cek streamUrl untuk TV atau URL standar untuk Voli/Futsal
    url = item.get("streamUrl", "") or item.get("url", "")
    if not url:
        return None
        
    try:
        # Gunakan GET dengan stream=True agar hemat kuota & cepat
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True, allow_redirects=True)
        
        # Jika status code di bawah 400 (200 OK, 302 Redirect, dll), berarti HIDUP
        if response.status_code < 400:
            return item
    except:
        pass
    return None

def process_file(filename):
    print(f"--- Memproses File: {filename} ---")
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # LOGIKA DETEKSI FORMAT
        is_obj_format = isinstance(data, dict) and "channels" in data
        items = data["channels"] if is_obj_format else data
        
        if not items:
            print(f"File {filename} sudah kosong atau bukan format list, melewati...")
            return

    except Exception as e:
        print(f"Error baca {filename}: {e}")
        return

    print(f"Mengecek {len(items)} link di {filename}...")
    
    valid_items = []
    # Gunakan 20 worker agar cepat tapi aman
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(check_link, items))
        valid_items = [i for i in results if i is not None]

    # SAFETY GUARD: JANGAN SIMPAN JIKA HASILNYA 0 (Mencegah playlist kosong total)
    if len(items) > 0 and len(valid_items) == 0:
        print(f"Peringatan: Semua link di {filename} dianggap mati. Data TIDAK akan diubah.")
        return

    # SIMPAN KEMBALI SESUAI FORMAT ASLINYA
    if is_obj_format:
        output_data = data
        output_data["channels"] = valid_items
    else:
        output_data = valid_items

    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)

    print(f"Pembersihan {filename} Selesai. Item aktif: {len(valid_items)}\n")

if __name__ == "__main__":
    print("Memulai NSTV TOTAL CLEANER (V3 - Safety Guard)...\n")
    for file in FILES_TO_CLEAN:
        process_file(file)
