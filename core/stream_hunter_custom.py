import time
import json
import re
import os
import threading
import asyncio
from urllib.parse import urlparse

import mitmproxy
import mitmproxy.options
from mitmproxy import http
from mitmproxy.tools.dump import DumpMaster
from selenium import webdriver  
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options

# --- GLOBAL VARIABLES PLAYLIST CONFIG ---
CAPTURED_URLS = set()
TARGET_HOMEPAGE = "https://livesports088.is"
WHITELIST_PATTERNS = re.compile(r'\.(m3u8|mpd)(\?.*)?$', re.IGNORECASE)
BLACKLIST_PATTERNS = re.compile(r'(ads|analytics|tracker|telemetry|doubleclick|pixel|api/stats|log)', re.IGNORECASE)
CURRENT_MATCH_TITLE = "Live Stream" 
CURRENT_MATCH_CATEGORY = "SPORTS" # Menampung kategori aktif per antrean

class MitmNetworkInterceptor:
    def request(self, flow: http.HTTPFlow) -> None:
        global CURRENT_MATCH_TITLE, CURRENT_MATCH_CATEGORY
        url = flow.request.pretty_url
        if BLACKLIST_PATTERNS.search(url):
            return
        if WHITELIST_PATTERNS.search(url) or "m3u8" in url.lower() or "mpd" in url.lower():
            referer = flow.request.headers.get("Referer", url)
            origin = flow.request.headers.get("Origin", f"https://{urlparse(url).netloc}")
            # Simpan judul dan kategori pertandingan aktif saat paket data disadap
            CAPTURED_URLS.add((url, referer, origin, CURRENT_MATCH_TITLE, CURRENT_MATCH_CATEGORY))

async def run_mitm_async():
    opts = mitmproxy.options.Options(listen_host='127.0.0.1', listen_port=8080)
    master = DumpMaster(opts)
    master.addons.add(MitmNetworkInterceptor())
    try:
        await master.run()
    except Exception:
        pass

def start_mitmproxy():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_mitm_async())

class MultiProxyStreamHunterV21:
    def __init__(self):
        self.match_queue = []

    def collect_inputs(self):
        print("====================================================")
        print("    MULTI-STREAM HUNTER v21 - CUSTOM CATEGORY       ")
        print("====================================================\n")
        print("[ℹ️] Masukkan rincian pertandingan satu per satu.")
        print("[ℹ️] Jika sudah selesai memasukkan semua link, ketik 'done' lalu Enter.\n")
        
        while True:
            url = input(f"Masukkan URL Laga Ke-{len(self.match_queue)+1} : ").strip()
            if url.lower() == 'done':
                break
            if not url:
                continue
                
            title = input(f"Masukkan Nama Laga Ke-{len(self.match_queue)+1} : ").strip()
            if not title:
                title = f"Live Match {len(self.match_queue)+1}"
                
            # --- PENAMBAHAN INPUT KATEGORI MANUAL ---
            category = input(f"Masukkan Kategori Laga Ke-{len(self.match_queue)+1} (Contoh: BOLA LIVE / VOLI LIVE) : ").strip()
            if not category:
                category = "SPORTS LIVE" # Fallback standar jika dikosongkan
                
            self.match_queue.append({"url": url, "title": title, "category": category.upper()})
            print("-" * 50)

    def run_hunter(self):
        self.collect_inputs()
        
        if not self.match_queue:
            print("[!] Daftar antrean kosong. Skrip dibatalkan.")
            return

        print("\n[*] Tahap 1: Mengaktifkan Core Proxy Pusat di Port 8080...")
        proxy_thread = threading.Thread(target=start_mitmproxy, daemon=True)
        proxy_thread.start()
        time.sleep(3)

        chrome_options = Options()
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--proxy-server=127.0.0.1:8080")
        chrome_options.add_argument("--ignore-certificate-errors")
        
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        global CURRENT_MATCH_TITLE, CURRENT_MATCH_CATEGORY
        total_laga = len(self.match_queue)
        
        for index, laga in enumerate(self.match_queue, 1):
            print(f"\n[*] Memproses Laga [{index}/{total_laga}]: {laga['title']} [{laga['category']}]")
            CURRENT_MATCH_TITLE = laga['title']
            CURRENT_MATCH_CATEGORY = laga['category'] # Mengoperasikan kategori dinamis ke interceptor
            
            driver = webdriver.Chrome(
                service=Service(ChromeDriverManager().install()), 
                options=chrome_options
            )
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            })

            driver.get(laga['url'])
            
            print(f"==========================================================================")
            print(f"[⚠️ ACTION REQUIRED]: Memproses Antrean Laga Ke-{index}: {laga['title']}")
            print(f"👉 Kategori Menu App: {laga['category']}")
            print(f"👉 1. Selesaikan puzzle captcha geser di layar Chrome.")
            print(f"👉 2. Klik tombol PLAY besar di tengah video sampai siaran stadion berputar.")
            print(f"==========================================================================")
            
            capture_duration = 30
            for sisa in range(capture_duration, 0, -5):
                print(f"[*] Proxy menyadap jaringan... Sisa waktu interaksi laga ini: {sisa} detik...")
                time.sleep(5)
                
            print(f"[+] Selesai merekam Laga Ke-{index}. Menutup browser...")
            driver.quit()

        self.export_to_custom_json()

    def export_to_custom_json(self):
        if not CAPTURED_URLS:
            print("\n[-] GAGAL TOTAL: Tidak ada satu pun berkas video .m3u8 yang lolos.")
            return

        forced_user_agent = "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 VLC/3.0 ExoPlayer/2.18"
        final_playlist = []
        
        unique_playlist = {}
        for uri, referer, origin, title, category in list(CAPTURED_URLS):
            unique_playlist[uri] = {"referer": referer, "origin": origin, "title": title, "category": category}

        for index, (uri, data) in enumerate(unique_playlist.items(), 1):
            drm_data = {"is_protected": False, "drm_type": "", "drm_key": ""}
            if "mpd" in uri.lower():
                drm_data = {"is_protected": True, "drm_type": "clearkey", "drm_key": "auto_detect_required_check_console"}

            item_structure = {
                "id": index,
                "title": f"{data['title']} - Server Live {index}",
                "category": data['category'], # Menggunakan isi kategori kustom inputan Anda
                "uri": uri,
                "user_agent": forced_user_agent,
                "is_live": True,
                "match_id": "IDN283_" + time.strftime("%Y%m%d"),
                "headers": {
                    "Referer": data["referer"],
                    "Origin": data["origin"]
                },
                "drm_info": drm_data,
                "epg_metadata": {
                    "tvg_id": f"idn283_multi_{index}.id",
                    "tvg_name": f"{data['title']} S{index}",
                    "tvg_logo": "https://livesports088.isfavicon.ico",
                    "source_xml": "Embedded"
                }
            }
            final_playlist.append(item_structure)

        file_output = "custom_format_playlist.json"
        with open(file_output, 'w', encoding='utf-8') as f:
            json.dump(final_playlist, f, indent=4, ensure_ascii=False)
            
        print(f"\n[+] PROSES SELESAI: BERHASIL MENGGABUNGKAN {len(final_playlist)} TAUTAN SEKALIGUS DENGAN KATEGORI KUSTOM!")
        print(f"👉 File Gabungan Tersimpan di: {os.path.abspath(file_output)}")

if __name__ == "__main__":
    hunter = MultiProxyStreamHunterV21()
    hunter.run_hunter()
