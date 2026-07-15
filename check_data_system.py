import urllib.request
import re
import concurrent.futures

# Konfigurasi URL sumber playlist m3u Anda
SOURCE_M3U_URL = "https://githubusercontent.com/dhasap/dhanytv/main/update-script/extra_channels.m3u"
OUTPUT_FILE = "system_config_utama.data"

def fetch_m3u(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Gagal mengunduh playlist: {e}")
        return ""

def parse_m3u(content):
    # Memisahkan berdasarkan blok entri saluran (EXTINF atau opsi lainnya)
    pattern = r'(#EXTVLCOPT:.*?#EXTINF:.*?)(?=^#EXTVLCOPT:|^#EXTINF:|\Z)'
    entries = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
    
    parsed_channels = []
    for entry in entries:
        # Ekstrak URL streaming (baris terakhir dari entri)
        lines = [line.strip() for line in entry.strip().split('\n') if line.strip()]
        if not lines:
            continue
        
        stream_url = lines[-1]
        if stream_url.startswith('http'):
            # Ambil semua teks headers/opsinya kecuali URL untuk rekonstruksi nanti
            header_part = "\n".join(lines[:-1])
            parsed_channels.append({
                "header": header_part,
                "url": stream_url
            })
    return parsed_channels

def check_link(channel):
    url = channel["url"]
    # Menangani skenario manifest MPD/M3U8 dengan request HEAD atau GET singkat
    try:
        req = urllib.request.Request(url, method='HEAD')
        # Tambahkan User-Agent standar agar tidak diblokir server
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status in:
                return channel
    except Exception:
        # Jika HEAD gagal, coba GET dengan batasan _byte range_ jika didukung
        try:
            req = urllib.request.Request(url, method='GET')
            req.add_header('User-Agent', 'Mozilla/5.0')
            req.add_header('Range', 'bytes=0-100')
            with urllib.request.urlopen(req, timeout=8) as response:
                if response.status in:
                    return channel
        except Exception:
            return None
    return None

def main():
    print("Memulai proses pengecekan...")
    raw_content = fetch_m3u(SOURCE_M3U_URL)
    if not raw_content:
        return

    channels = parse_m3u(raw_content)
    print(f"Ditemukan {len(channels)} saluran untuk dicek.")

    live_channels = []
    # Menggunakan ThreadPool untuk pengecekan cepat secara paralel
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        results = executor.map(check_link, channels)
        for result in results:
            if result:
                live_channels.append(result)

    # Tulis hasil saluran yang aktif ke berkas m3u baru
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in live_channels:
            f.write(f"{ch['header']}\n{ch['url']}\n")

    print(f"Selesai! {len(live_channels)} saluran aktif disimpan ke {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
