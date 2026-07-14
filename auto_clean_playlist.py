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
            # Menangani format object {"channels": []} atau format list []
            items = data["channels"] if isinstance(data, dict) and "channels" in data else data
    except Exception as e:
        print(f"Melewati {filename}: {e}")
        return

    print(f"Total awal di {filename}: {len(items)}")
    
    # Cek link secara paralel (30 worker agar cepat)
    valid_items = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(check_link, items))
        valid_items = [i for i in results if i is not None]

    # Simpan kembali sesuai format aslinya
    output_data = {"channels": valid_items} if isinstance(data, dict) and "channels" in data else valid_items
    with open(filename, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Pembersihan {filename} Selesai. Item aktif: {len(valid_items)}\n")

def main():
    print("Memulai NSTV TOTAL CLEANER...\n")
    for file in FILES_TO_CLEAN:
        process_file(file)
    print("Semua playlist telah dibersihkan!")

if __name__ == "__main__":
    main()
