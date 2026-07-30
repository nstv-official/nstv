import asyncio
import json
import re
import base64
import requests
import os
import random
from datetime import datetime, timedelta

# Gunakan playwright.async_api secara langsung
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# ==============================================================================
# SYSTEM CONFIGURATION (V17.2 - PERFECT SNIFFING & LINK RETRIEVAL)
# ==============================================================================
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_OWNER = "nstv-official"
REPO_NAME = "nstv"
MANIFEST_PATH = "manifest_v4.json"

MAX_CONCURRENT_TABS = 3
GITHUB_RETRY_LIMIT = 5
HUNTING_TIMEOUT = 25

# Environment Detection
IS_CLOUD = os.getenv("GITHUB_ACTIONS") == "true"
# v17.2: Buka browser jika di laptop (Lokal)
HEADLESS_MODE = True if IS_CLOUD else False

if IS_CLOUD:
    SESSION_DIR = "./internal_cache"; LOCAL_MANIFEST = MANIFEST_PATH
else:
    SESSION_DIR = r"D:\NSTV_Internal_Cache"
    LOCAL_MANIFEST = os.path.join(os.path.dirname(os.path.dirname(__file__)), MANIFEST_PATH)

def get_now_wib():
    """Mengembalikan waktu WIB (Naive) untuk perbandingan yang aman (v17.2)."""
    from datetime import timezone
    return (datetime.now(timezone.utc) + timedelta(hours=7)).replace(tzinfo=None)

# Permanent System Entries
FIXED_ENTRIES = [
    {
        "id": "sys_v6_relay",
        "title": "📺 VTV6 HD (Sports - 24/7)",
        "category": "SYSTEM CHANNEL",
        "uri": "http://125hvt.ddns.net:21585/vtv6/playlist.m3u8",
        "is_live": True,
        "match_time": "24/7",
        "headers": {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
        "drm_info": { "is_protected": False, "drm_type": "", "drm_key": "" },
        "epg_metadata": { "tvg_id": "v6.relay", "tvg_name": "VTV6", "tvg_logo": "https://raw.githubusercontent.com/nstv-official/nstv/main/logos/vtv6.png", "source_xml": "Embedded" }
    }
]

PRIORITY_GROUPS = ["Borneo", "Persis", "Persib", "Persija", "Arema", "PSM", "Persebaya", "Indonesia", "Presiden", "Hyundai", "Asean", "AFF"]

# v17.2 Esport Killer List
BLOCK_LIST = [
    "lol", "esports", "lck", "lpl", "gen g", "t1", "dota", "gaming", "valorant", "pubg", "mlbb", "pga", "golf",
    "bestia", "galorys", "zero tenacity", "level up", "spirit", "vitality", "faze", "g2", "liquid",
    "natus vincere", "cs:go", "cs2", "blast", "esl", "simul", "simulation"
]

ENDPOINTS = ["https://xoilaczzggz.tv", "https://xoilacxtu.tv"]
DEFAULT_ASSET = "https://raw.githubusercontent.com/nstv-official/nstv/main/logos/default.png"

def remove_accents(input_str):
    s1 = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    s0 = "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    result = input_str.lower()
    for i in range(len(s1)): result = result.replace(s1[i], s0[i])
    return result

def parse_registry_slug(slug):
    """Mengekstrak nama tim, jam, dan tanggal (v17.2)."""
    slug_clean = slug.strip("/").split("/")[-1]
    time_match = re.search(r'luc-(\d{2})(\d{2})', slug_clean)
    m_time = f"{time_match.group(1)}:{time_match.group(2)}" if time_match else "LIVE"
    date_match = re.search(r'ngay-(\d{2})-(\d{2})-(\d{4})', slug_clean)
    m_date = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}" if date_match else "00000000"
    team_part = slug_clean.split("-luc-")[0]
    clean_label = team_part.replace("-vs-", " VS ").replace("-", " ")
    return clean_label.title(), m_time, m_date

def get_entry_icon(label):
    t = label.lower()
    if any(x in t for x in ["voli", "volleyball", "bong chuyen"]): return "🏐"
    if any(x in t for x in ["badminton", "bwf", "cau long"]): return "🏸"
    if any(x in t for x in ["tennis"]): return "🎾"
    return "⚽"

def resolve_asset_url(category, assets_list):
    cat_norm = category.lower().replace(" ", "_")
    filename = f"{cat_norm}.png"
    if filename in assets_list: return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/logos/{filename}"
    if "football" in cat_norm or "presiden" in cat_norm:
        if "football.png" in assets_list: return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/logos/football.png"
    return DEFAULT_ASSET

async def fetch_registry_state():
    """Mengambil data manifest yang sudah ada di GitHub (v17.2)."""
    if not GITHUB_TOKEN: return {}
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{MANIFEST_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            data = json.loads(content)
            return {m["id"]: m for m in data}
    except: pass
    return {}

def get_remote_assets():
    """Mendapatkan daftar file logo dari GitHub (v17.2)."""
    if not GITHUB_TOKEN: return []
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/logos"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            return [file["name"].lower() for file in r.json() if file["name"].endswith(".png")]
    except: pass
    return []

def check_entry_validity(m_time, m_date, now):
    """Loloskan semua laga yang muncul di halaman depan website (v17.2)."""
    return True

def commit_to_storage(content):
    if not GITHUB_TOKEN: return False
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{MANIFEST_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    for attempt in range(GITHUB_RETRY_LIMIT):
        try:
            r = requests.get(api_url, headers=headers)
            sha = r.json().get("sha") if r.status_code == 200 else None
            payload = {
                "message": f"System Registry Sync {get_now_wib().strftime('%Y-%m-%d %H:%M')}",
                "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")
            }
            if sha: payload["sha"] = sha
            res = requests.put(api_url, headers=headers, json=payload)
            if res.status_code in [200, 201]: return True
            import time; time.sleep(random.uniform(1, 3))
        except: break
    return False

def finalize_sync(registry):
    """Menyimpan data (v17.2 - Sniper Mode: Hanya yang ada link)."""
    now = get_now_wib()
    final_list = []

    # SNIPER: Hanya ambil yang sudah ada Link (URI)
    for x in registry.values():
        if x.get("id", "").startswith("sys_v6"):
            final_list.append(x); continue

        has_link = x.get("uri", "").strip() != ""
        if has_link:
            x["is_live"] = True
            final_list.append(x)

    def sort_logic(x):
        if x.get("id", "").startswith("sys_v6"): return (0, 0, 0)
        cat = x.get("category", "").upper()
        prio_cat = 1 if "PRESIDEN" in cat else (2 if "ASEAN" in cat else 3)
        m_time = x.get("match_time", "99:99")
        try:
            t_obj = datetime.strptime(m_time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
            return (1, prio_cat, abs((now - t_obj).total_seconds()))
        except: return (2, prio_cat, 999999)

    final_list.sort(key=sort_logic)
    content = json.dumps(final_list, indent=4)
    try:
        with open(LOCAL_MANIFEST, "w", encoding="utf-8") as f: f.write(content)
        print(f"    [SNIPER] {len(final_list)} active matches synced.")
    except Exception as e: print(f"    [!] Gagal simpan: {e}")
    commit_to_storage(content)

async def process_entry_manifest(context, info, registry, semaphore):
    """Proses perburuan link (v17.2 - Global Sniffing)."""
    m_url = info["url"]; m_id = info["id"]; m_title = info.get("title", "Unknown")
    async with semaphore:
        print(f"    [>>>] Menyerbu Link: {m_title}...")
        for attempt in range(2):
            page = await context.new_page()
            try:
                await Stealth().apply_stealth_async(page)

                uri = ""; headers = {}
                BAD = ["ads", "analytics", "pixel", "telemetry", "log", "doubleclick", "histats", "collector", "popunder"]

                # v17.2: Pasang telinga di level CONTEXT agar menangkap dari SELURUH frame
                async def sniffer(request):
                    nonlocal uri, headers
                    if uri: return
                    u = request.url
                    # Filter Video Extensions
                    if any(ext in u.lower() for ext in [".m3u8", ".mpd", ".flv", ".ts"]):
                        if not u.startswith("blob:") and not any(k in u.lower() for k in BAD):
                            uri = u
                            headers = dict(request.headers)
                            print(f"    [HIT] Link video terdeteksi!")

                context.on("request", sniffer)

                await page.goto(m_url, wait_until="commit", timeout=35000)
                await page.mouse.wheel(0, 400); await asyncio.sleep(2); await page.mouse.wheel(0, -400)

                for i in range(20):
                    if uri: break
                    if i in [3, 8, 15]:
                        # Klik beruntun di frame utama dan frame pertama
                        target_frames = [page.main_frame]
                        if len(page.frames) > 1: target_frames.append(page.frames[1])

                        for frame in target_frames:
                            for s in ["button.vjs-big-play-button", ".play-icon", "text=Play", "text=Server 1", "text=HLS"]:
                                try:
                                    btn = await frame.query_selector(s)
                                    if btn: await btn.click()
                                except: pass
                    await asyncio.sleep(1)

                context.remove_listener("request", sniffer)

                if uri:
                    registry[m_id]["uri"] = f"{uri}{'&' if '?' in uri else '?'}sys_cache={int(get_now_wib().timestamp())}"
                    registry[m_id]["is_live"] = True
                    registry[m_id]["headers"] = headers
                    print(f"    [BERHASIL] Link siap saji!")
                    return True

                if attempt == 0: print(f"    [RETRY] Mencoba ulang halaman...")
            except Exception as e:
                print(f"    [!] Error tab: {str(e)[:50]}")
            finally:
                await page.close()

        print(f"    [ZONK] Gagal."); return False

async def run_sync_cycle():
    if not os.path.exists(SESSION_DIR): os.makedirs(SESSION_DIR)
    now = get_now_wib()
    print(f"[SYSTEM] Memulai Siklus V17.2 (VISUAL DEBUG) - WIB: {now.strftime('%H:%M')}...")
    state = await fetch_registry_state()
    registry = {}; assets = get_remote_assets()
    for entry in FIXED_ENTRIES: registry[entry["id"]] = entry

    async with async_playwright() as p:
        launch_kwargs = {"headless": HEADLESS_MODE}
        if not HEADLESS_MODE: launch_kwargs["slow_mo"] = 500

        browser = await p.chromium.launch(**launch_kwargs)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", ignore_https_errors=True)
        queue = []
        for endpoint in ENDPOINTS:
            page = await context.new_page()
            try:
                print(f"[*] Memindai: {endpoint}...")
                await page.goto(endpoint, wait_until="load", timeout=60000)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(5)
                nodes = await page.query_selector_all("a[href*='truc-tiep']")
                print(f"    [OK] Ditemukan {len(nodes)} link.")
                seen = set()
                for node in nodes:
                    try:
                        href = await node.get_attribute("href")
                        if not href: continue
                        full_url = href if href.startswith("http") else endpoint.rstrip("/") + "/" + href.lstrip("/")
                        slug = full_url.strip("/").split("/")[-1]
                        if not slug or slug in seen or any(k in slug.lower() for k in BLOCK_LIST) or slug.isdigit(): continue
                        seen.add(slug)
                        label, m_time, m_date = parse_registry_slug(slug)
                        m_id = f"sys_{m_date}_{slug.replace('-', '_').split('_luc_')[0]}"

                        cat = "FOOTBALL"
                        if any(k in label.lower() for k in ["presiden", "president"]): cat = "PIALA PRESIDEN"
                        elif any(k in label.lower() for k in ["badminton", "cau long"]): cat = "BADMINTON"

                        registry[m_id] = {
                            "id": m_id, "title": f"{get_entry_icon(label)} {label}",
                            "category": cat, "uri": state.get(m_id, {}).get("uri", ""), "is_live": False,
                            "match_time": m_time, "headers": {"User-Agent": "Mozilla/5.0"},
                            "drm_info": {"is_protected": False, "drm_type": "", "drm_key": ""},
                            "epg_metadata": {"tvg_id": m_id, "tvg_name": label, "tvg_logo": resolve_asset_url(cat, assets), "source_xml": "Embedded"}
                        }
                        try:
                            t_obj = datetime.strptime(m_time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
                            if now >= (t_obj - timedelta(minutes=15)) and not registry[m_id]["uri"]:
                                queue.append({"id": m_id, "url": full_url, "title": label})
                        except: pass
                    except: continue
            except Exception as e: print(f"    [!] Error radar: {e}")
            finally: await page.close()

        if queue:
            print(f"[CORE] Menyerbu {len(queue)} laga secara PARALEL...")
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)
            await asyncio.gather(*(process_entry_manifest(context, item, registry, semaphore) for item in queue[:20]), return_exceptions=True)

        finalize_sync(registry)
        await browser.close()
        print(f"[SYSTEM] Siklus selesai pada {get_now_wib().strftime('%H:%M')}.\n")

async def main():
    if IS_CLOUD: await run_sync_cycle()
    else:
        while True:
            await run_sync_cycle(); await asyncio.sleep(60)

if __name__ == "__main__": asyncio.run(main())
