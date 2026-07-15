import urllib.request
import re
import concurrent.futures

# Ganti dengan URL m3u Anda sendiri
SOURCE_M3U_URL = "https://raw.githubusercontent.com/dhasap/dhanytv/refs/heads/main/update-script/extra_channels.m3u"
OUTPUT_FILE = "system_data.dt"

def fetch_m3u(url):
    try:
        # Tambahkan User-Agent saat mengunduh m3u agar tidak diblokir GitHub/Cloudflare
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as response:
            return response.read().decode('utf-8')
    except Exception as e:
        print(f"Gagal mengunduh playlist: {e}")
        return ""

def parse_m3u(content):
    # Regex yang jauh lebih aman untuk menangkap blok multi-baris yang diawali #EXTVLCOPT atau #KODIPROP
    pattern = r'((?:#EXTVLCOPT|#KODIPROP|#EXTINF).*?)(?=^#EXTVLCOPT:|^#KODIPROP:|^#EXTINF:|\Z)'
    blocks = re.findall(pattern, content, re.MULTILINE | re.DOTALL)
    
    parsed_channels = []
    for block in blocks:
        lines = [line.strip() for line in block.split('\n') if line.strip()]
        if not lines:
            continue
        
        # Baris terakhir wajib berupa URL streaming (http atau https)
        stream_url = lines[-1]
        if stream_url.startswith('http'):
            header_part = "\n".join(lines[:-1])
            parsed_channels.append({
                "header": header_part,
                "url": stream_url
            })
    return parsed_channels

def check_link(channel):
    url = channel["url"]
    # 200: OK, 201: Created, 206: Partial Content (Sering muncul di rentang byte GET)
    valid_statuses = [200, 201, 206]
    
    # Untuk tautan MPD (.mpd) atau tautan berproteksi DRM, request HEAD sering ditolak (403/405).
    # Maka kita prioritaskan langsung menggunakan GET kecil (mengambil beberapa byte saja).
    try:
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        req.add_header('Range', 'bytes=0-1024') # Ambil 1KB pertama saja untuk verifikasi keaktifan
        
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status in valid_statuses:
                return channel
    except Exception:
        # Metode cadangan jika server tidak mendukung header 'Range'
        try:
            req = urllib.request.Request(url, method='HEAD')
            req.add_header('User-Agent', 'Mozilla/5.0')
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status in valid_statuses:
                    return channel
        except Exception:
            return None
    return None

def main():
    print("Memulai proses pengecekan...")
    raw_content = fetch_m3u(SOURCE_M3U_URL)
    if not raw_content:
        print("Konten m3u kosong atau tidak dapat diakses.")
        return

    channels = parse_m3u(raw_content)
    print(f"Ditemukan {len(channels)} saluran dari repositori sumber.")

    if not channels:
        print("Gagal mengekstrak saluran. Periksa format berkas m3u Anda.")
        return

    live_channels = []
    # Membatasi max_workers ke 5 agar server penyedia tidak mendeteksi ini sebagai serangan DDoS
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = executor.map(check_link, channels)
        for result in list(results):
            if result:
                live_channels.append(result)

    # Tulis ulang berkas hasil dengan struktur m3u yang benar
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for ch in live_channels:
            f.write(f"{ch['header']}\n{ch['url']}\n")

    print(f"Selesai! {len(live_channels)} saluran aktif berhasil disimpan ke {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
