import requests
import json
import concurrent.futures

# DAFTAR FILE YANG AKAN DIBERSIHKAN
FILES_TO_CLEAN = ["playlist.json", "voli.json", "futsal.json"]
TIMEOUT = 10

def check_link(item):
    # Cek streamUrl untuk TV atau URL standar untuk Voli/Futsal
    url = item.get("streamUrl", "") or item.get("url", "")
    if not url:
        return None
    try:
        # Cek hanya header saja agar cepat
        response = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code < 400:
            return item
    except:
        pass
    return None

def process_file(filename):
    print(f"--- Memproses File: {filename} ---")
    try:
        with open(filename, 'r') as f:
            data = json.load(f)
        
        # LOGIKA DETEKSI FORMAT (PENTING!)
        is_obj_format = isinstance(data, dict) and "channels" in data
        items = data["channels"] if is_obj_format else data
        
        if not isinstance(items, list):
            print(f"Format di {filename} tidak didukung.")
            return

    except Exception as e:
        print(f"Melewati {filename}: {e}")
        return

    print(f"Total awal di {filename}: {len(items)}")
    
    # Cek link secara paralel (30 worker agar cepat)
    valid_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(check_link, items))
        valid_items = [i for i in results if i is not None]

    # SIMPAN KEMBALI SESUAI FORMAT ASLINYA (TANPA MERUSAK STRUKTUR)
    if is_obj_format:
        output_data = data
        output_data["channels"] = valid_items
    else:
        output_data = valid_items

    with open(filename, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Pembersihan {filename} Selesai. Item aktif: {len(valid_items)}\n")

def main():
    print("Memulai NSTV TOTAL CLEANER (V2 - Smart Format)...\n")
    for file in FILES_TO_CLEAN:
        process_file(file)
    print("Semua playlist telah dibersihkan dan struktur tetap terjaga!")

if __name__ == "__main__":
    main()
