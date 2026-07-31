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
# SYSTEM CONFIGURATION (V18.2 - THE GUARDIAN & AD-DESTROYER)
# ==============================================================================
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_OWNER = "nstv-official"
REPO_NAME = "nstv"
MANIFEST_PATH = "manifest_v4.json"

MAX_CONCURRENT_TABS = 3
GITHUB_RETRY_LIMIT = 5
HUNTING_TIMEOUT = 25

# Gembok Digital untuk Sinkronisasi Atomik
commit_lock = asyncio.Lock()

# Environment Detection
IS_CLOUD = os.getenv("GITHUB_ACTIONS") == "true"
HEADLESS_MODE = True if IS_CLOUD else False

if IS_CLOUD:
    SESSION_DIR = "./internal_cache"; LOCAL_MANIFEST = MANIFEST_PATH
else:
    SESSION_DIR = r"D:\NSTV_Internal_Cache"
    LOCAL_MANIFEST = os.path.join(os.path.dirname(os.path.dirname(__file__)), MANIFEST_PATH)

def get_now_wib():
    """Mengembalikan waktu WIB (Naive) untuk perbandingan yang aman (v18.2)."""
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

PRIORITY_GROUPS = ["Borneo", "juventus", "Persis", "Persib", "Persija", "Arema", "PSM", "Persebaya", "Indonesia", "Presiden", "Hyundai", "Asean", "AFF"]

# v18.2 Massive Block List (Esport, Simulation, Ads)
BLOCK_LIST = [
    "lol", "esports", "lck", "lpl", "gen g", "t1", "nba", "dota", "gaming", "valorant", "pubg", "mlbb", "pga", "golf",
    "bestia", "galorys", "zero tenacity", "level up", "spirit", "vitality", "faze", "g2", "liquid",
    "natus vincere", "cs:go", "cs2", "blast", "esl", "simul", "simulation", "score-only", "graph", "analysis"
]

# Tambahkan Tigoals sebagai sumber utama
ENDPOINTS = ["https://idn283.livesports088.is", "https://azabuglobal.com"]
DEFAULT_ASSET = "https://raw.githubusercontent.com/nstv-official/nstv/main/logos/default.png"

def remove_accents(input_str):
    s1 = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    s0 = "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    result = input_str.lower()
    for i in range(len(s1)): result = result.replace(s1[i], s0[i])
    return result

def parse_registry_slug(slug):
    """Mengekstrak nama tim, jam, dan tanggal (v18.2 - Multi-Pattern)."""
    slug_clean = slug.strip("/").split("/")[-1]

    # 1. Cari Waktu: luc-1530 atau pola Xoilac
    time_match = re.search(r'luc-(\d{2})(\d{2})', slug_clean)
    m_time = f"{time_match.group(1)}:{time_match.group(2)}" if time_match else "LIVE"

    # 2. Cari Tanggal
    date_match = re.search(r'ngay-(\d{2})-(\d{2})-(\d{4})', slug_clean)
    m_date = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}" if date_match else "00000000"

    # 3. Bersihkan Nama Tim (Dukung pola tigoals: 3040323-arema-fc-vs-dpmm-fc)
    team_part = slug_clean.split("-luc-")[0]
    # Jika ada pola ID-nama di depan (tigoals), buang angka ID dan tanda hubung pertama
    team_part = re.sub(r'^\d+-', '', team_part)

    clean_label = team_part.replace(".html", "").replace("-vs-", " VS ").replace("-", " ")

    replacements = {
        r"\bnu\b": "Women", r"\bopmm\b": "DPMM", r"\bfc\b": "FC", r"\bpsm\b": "PSM",
        r"\barema\b": "AREMA", r"\baff\b": "AFF", r"\bbwf\b": "BWF"
    }
    for pattern, repl in replacements.items():
        clean_label = re.sub(pattern, repl, clean_label, flags=re.IGNORECASE)
    return clean_label.title(), m_time, m_date

def get_entry_icon(label, category):
    """v18.2: Ikon Akurat berdasarkan Kategori dan Kamus Atlet."""
    t = label.lower()
    c = category.upper()
    if "VOLLEY" in c: return "🏐"
    if "BADMINTON" in c: return "🏸"
    if "TENNIS" in c: return "🎾"
    if "MOTOR" in c: return "🏎️"
    if "FUTSAL" in c: return "🏟️"
    if any(x in t for x in ["voli", "v-cup", "volleyball", "bong chuyen"]): return "🏐"
    if any(x in t for x in ["badminton", "bwf", "cau long", "wenyu", "ginting", "jonatan"]): return "🏸"
    if any(x in t for x in ["tennis", "atmane", "tabilo", "minaur", "hewitt", "kalinskaya", "tjen"]): return "🎾"
    if any(x in t for x in ["gp", "f1", "dua xe", "motogp"]): return "🏎️"
    return "⚽"

def resolve_asset_url(category, assets_list):
    cat_norm = category.lower().replace(" ", "_")
    filename = f"{cat_norm}.png"
    if filename in assets_list: return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/logos/{filename}"
    if "football" in cat_norm or "presiden" in cat_norm or "asean" in cat_norm:
        if "football.png" in assets_list: return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/logos/football.png"
    return DEFAULT_ASSET

async def fetch_registry_state():
    if not GITHUB_TOKEN: return {}
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{MANIFEST_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200:
            content = base64.b64decode(r.json()["content"]).decode("utf-8")
            return {m["id"]: m for m in json.loads(content)}
    except: pass
    return {}

def get_remote_assets():
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
    return True

async def commit_to_storage(content):
    if not GITHUB_TOKEN: return False
    async with commit_lock:
        api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{MANIFEST_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
        for attempt in range(GITHUB_RETRY_LIMIT):
            try:
                r = requests.get(api_url, headers=headers)
                sha = r.json().get("sha") if r.status_code == 200 else None
                payload = {"message": f"System Registry Sync {get_now_wib().strftime('%Y-%m-%d %H:%M')}", "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")}
                if sha: payload["sha"] = sha
                res = requests.put(api_url, headers=headers, json=payload)
                if res.status_code in [200, 201]:
                    print(f"    [OK] GitHub Updated (Attempt {attempt+1})")
                    return True
                await asyncio.sleep(random.uniform(1, 3))
            except: break
    return False

def normalize_uri(uri):
    if not uri: return ""
    return uri.split('?')[0].split('&')[0]

async def finalize_sync(registry):
    """v18.2: The Guardian - Lindungi data dari update kosong."""
    now = get_now_wib()
    active_matches = []
    for x in registry.values():
        if x.get("id", "").startswith("sys_v6"):
            active_matches.append(x); continue
        if x.get("uri", "").strip() != "":
            x["is_live"] = True
            active_matches.append(x)

    # DEDUP & FILTER
    unique_by_base_uri = {}
    for match in active_matches:
        base_uri = normalize_uri(match.get("uri"))
        if not base_uri: continue
        if base_uri not in unique_by_base_uri:
            unique_by_base_uri[base_uri] = match
        else:
            existing = unique_by_base_uri[base_uri]
            def get_m_score(m):
                title = m.get("title", "").upper()
                s = 0
                if any(k.upper() in title for k in PRIORITY_GROUPS): s += 10
                if "INDONESIA" in title: s += 50
                return s
            if get_m_score(match) > get_m_score(existing): unique_by_base_uri[base_uri] = match

    final_list = list(unique_by_base_uri.values())

    # [GUARDIAN] v18.2: Batalkan sinkronisasi jika data baru KOSONG (Hanya VTV6)
    if len(final_list) <= 1:
        if not IS_CLOUD: print("    [GUARDIAN] Data baru kosong, membatalkan simpan untuk lindungi data lama.")
        return

    final_list.sort(key=lambda x: (x.get("id", "").startswith("sys_v6")==False, "INDONESIA" not in x.get("title", "").upper(), abs((now - datetime.strptime(x.get("match_time", "00:00"), "%H:%M").replace(year=now.year, month=now.month, day=now.day)).total_seconds()) if ":" in x.get("match_time", "") else 999999))

    content = json.dumps(final_list, indent=4)
    try:
        with open(LOCAL_MANIFEST, "w", encoding="utf-8") as f: f.write(content)
    except: pass
    await commit_to_storage(content)

async def process_entry_manifest(context, info, registry, semaphore):
    """v18.2: Tigoals Hunter Engine (Atomic Sync)."""
    m_url = info["url"]; m_id = info["id"]; m_title = info.get("title", "Unknown")
    async with semaphore:
        print(f"    [>>>] Menyerbu Link: {m_title}...")
        for attempt in range(2):
            page = await context.new_page()
            try:
                await Stealth().apply_stealth_async(page)
                uri = ""; headers = {}
                BAD = ["ads", "analytics", "pixel", "telemetry", "log", "doubleclick", "histats", "collector"]
                async def sniffer(request):
                    nonlocal uri, headers
                    if uri: return
                    u = request.url
                    if any(ext in u.lower() for ext in [".m3u8", ".mpd", ".flv", ".ts"]):
                        if not u.startswith("blob:") and not any(k in u.lower() for k in BAD):
                            uri = u; headers = dict(request.headers)
                            print(f"    [HIT] Link video terdeteksi!")
                context.on("request", sniffer)
                await page.goto(m_url, wait_until="commit", timeout=40000)
                await page.mouse.wheel(0, 400); await asyncio.sleep(2); await page.mouse.wheel(0, -400)
                for i in range(20):
                    if uri: break
                    if i in [3, 8, 15]:
                        # Klik Play & Tigoals Server Buttons (Live1)
                        for frame in [page.main_frame] + page.frames:
                            for s in ["button.vjs-big-play-button", ".play-icon", "text=Play", "text=Live1", "text=Server 1"]:
                                try:
                                    btn = await frame.query_selector(s)
                                    if btn: await btn.click()
                                except: pass
                    await asyncio.sleep(1)
                context.remove_listener("request", sniffer)
                if uri:
                    registry[m_id]["uri"] = f"{uri}{'&' if '?' in uri else '?'}sys_cache={int(get_now_wib().timestamp())}"
                    registry[m_id]["is_live"] = True; registry[m_id]["headers"] = headers
                    print(f"    [BERHASIL] {m_title} Siap Saji!")
                    await finalize_sync(registry)
                    return True
            except: pass
            finally: await page.close()
        print(f"    [ZONK] Gagal."); return False

async def run_sync_cycle():
    if not os.path.exists(SESSION_DIR): os.makedirs(SESSION_DIR)
    now = get_now_wib()
    print(f"[SYSTEM] Memulai Siklus V18.2 (THE GUARDIAN) - WIB: {now.strftime('%H:%M')}...")
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
                await asyncio.sleep(5)

                # Ad-Destroyer (Livesports088)
                if "livesports088" in endpoint:
                    try:
                        await page.keyboard.press("Escape")
                        for s in ["text='X'", "text='Close'", ".close-icon", ".ad-close", "#close-button"]:
                            btn = await page.query_selector(s)
                            if btn: await btn.click(); break
                        await asyncio.sleep(3)
                    except: pass

                # Selector Universal
                nodes = await page.query_selector_all("a[href*='match'], a[href*='truc-tiep'], a[href*='html']")
                print(f"    [OK] Ditemukan {len(nodes)} elemen potensial.")
                seen = set()
                for node in nodes:
                    try:
                        href = await node.get_attribute("href")
                        if not href or not any(k in href.lower() for k in ["vs", "match", "live", "truc-tiep"]): continue
                        full_url = href if href.startswith("http") else endpoint.rstrip("/") + "/" + href.lstrip("/")
                        slug = full_url.strip("/").split("/")[-1]
                        if slug in seen or any(k in slug.lower() for k in BLOCK_LIST) or slug.isdigit(): continue
                        seen.add(slug)
                        label, m_time, m_date = parse_registry_slug(slug)
                        m_id = f"sys_{m_date}_{slug.replace('-', '_').split('.')[0]}"

                        cat = "FOOTBALL"
                        l_lower = label.lower()
                        if any(k in l_lower for k in ["presiden", "president"]): cat = "PIALA PRESIDEN INDONESIA"
                        elif any(k in l_lower for k in ["badminton", "cau long"]): cat = "BADMINTON"
                        elif any(k in l_lower for k in ["asean", "aff"]): cat = "ASEAN CHAMPIONSHIP"

                        registry[m_id] = {
                            "id": m_id, "title": f"{get_entry_icon(label, cat)} {label}",
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
        await finalize_sync(registry)
        await browser.close()
        print(f"[SYSTEM] Siklus selesai pada {get_now_wib().strftime('%H:%M')}.\n")

async def main():
    if IS_CLOUD: await run_sync_cycle()
    else:
        while True:
            await run_sync_cycle(); await asyncio.sleep(60)

if __name__ == "__main__": asyncio.run(main())
