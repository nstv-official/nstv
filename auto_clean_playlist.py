import requests
import json
import concurrent.futures

# Konfigurasi
INPUT_FILE = "playlist.json"
OUTPUT_FILE = "playlist.json"
TIMEOUT = 10

def check_link(channel):
    url = channel.get("streamUrl", "")
    if not url:
        return None
    try:
        # Cek hanya header saja agar cepat
        response = requests.head(url, timeout=TIMEOUT, allow_redirects=True)
        if response.status_code < 400:
            return channel
    except:
        pass
    return None

def main():
    print("Memulai proses pembersihan playlist...")
    try:
        with open(INPUT_FILE, 'r') as f:
            data = json.load(f)
            # Menangani format object {"channels": []} atau format list []
            channels = data["channels"] if isinstance(data, dict) and "channels" in data else data
    except Exception as e:
        print(f"Gagal membaca file: {e}")
        return

    print(f"Total channel awal: {len(channels)}")
    
    # Cek link secara paralel (30 worker agar cepat)
    valid_channels = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        results = list(executor.map(check_link, channels))
        valid_channels = [c for c in results if c is not None]

    # Simpan kembali sesuai format aslinous
    output_data = {"channels": valid_channels}
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Pembersihan selesai. Channel aktif: {len(valid_channels)}")

if __name__ == "__main__":
    main()
