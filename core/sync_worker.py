import asyncio
import json
import re
import base64
import requests
import os
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# ==============================================================================
# SYSTEM CONFIGURATION (V16.3 - STABLE OMNI-RADAR & VISIBLE SCHEDULE)
# ==============================================================================
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_OWNER = "nstv-official"
REPO_NAME = "nstv"
MANIFEST_PATH = "manifest_v4.json"

# Performance Tuning
MAX_CONCURRENT_TABS = 3
GITHUB_RETRY_LIMIT = 5
HUNTING_TIMEOUT = 25

# Environment Detection
IS_CLOUD = os.getenv("GITHUB_ACTIONS") == "true"
HEADLESS_MODE = True

# Path Management
if IS_CLOUD:
    SESSION_DIR = "./internal_cache"; LOCAL_MANIFEST = MANIFEST_PATH
else:
    SESSION_DIR = r"D:\NSTV_Internal_Cache"
    LOCAL_MANIFEST = os.path.join(os.path.dirname(os.path.dirname(__file__)), MANIFEST_PATH)

def get_now_wib():
    """Selalu paksa waktu ke WIB (GMT+7) (v16.3)."""
    from datetime import timezone
    return datetime.now(timezone.utc) + timedelta(hours=7)

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

# Classification Keywords
PRIORITY_GROUPS = ["Borneo", "Persis", "Persib", "Persija", "Arema", "PSM", "Persebaya", "Indonesia", "Presiden", "Hyundai", "Asean", "AFF"]
TARGET_SPORTS = ["bong da", "football", "soccer", "cau long", "badminton", "bong chuyen", "volleyball", "futsal", "dua xe", "motogp", "tennis", "quan vot"]
ATHLETE_KEYWORDS = ["wenyu", "supak", "ginting", "jonatan", "fajar", "riani", "setiawan", "ahsan", "ankul", "sen", "vitidsarn", "antonsen"]
BLOCK_LIST = ["lol", "esports", "lck", "lpl", "gen g", "t1", "dota", "gaming", "valorant", "pubg", "mlbb", "pga", "golf", "bestia", "galorys", "cs:go", "cs2"]
ENDPOINTS = ["https://xoilaczzggz.tv", "https://xoilacxtu.tv"]
DEFAULT_ASSET = "https://raw.githubusercontent.com/nstv-official/nstv/main/logos/default_logo.png"
# ==============================================================================

def remove_accents(input_str):
    s1 = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    s0 = "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    result = input_str.lower()
    for i in range(len(s1)): result = result.replace(s1[i], s0[i])
    return result

def parse_registry_slug(slug):
    slug_clean = slug.strip("/").split("/")[-1]
    time_match = re.search(r'luc-(\d{2})(\d{2})', slug_clean)
    m_time = f"{time_match.group(1)}:{time_match.group(2)}" if time_match else "LIVE"
    date_match = re.search(r'ngay-(\d{2})-(\d{2})-(\d{4})', slug_clean)
    m_date = f"{date_match.group(1)}{date_match.group(2)}{date_match.group(3)}" if date_match else "00000000"
    team_part = slug_clean.split("-luc-")[0]
    clean_label = team_part.replace("-vs-", " VS ").replace("-", " ")
    replacements = {
        r"\bnu\b": "Women", r"\bopmm\b": "DPMM", r"\bfc\b": "FC", r"\bpsm\b": "PSM",
        r"\barema\b": "AREMA", r"\baff\b": "AFF", r"\bbwf\b": "BWF"
    }
    for pattern, repl in replacements.items():
        clean_label = re.sub(pattern, repl, clean_label, flags=re.IGNORECASE)
    return clean_label.title(), m_time, m_date

def get_entry_icon(label):
    t = label.lower()
    if any(x in t for x in ["voli", "volleyball", "bong chuyen"]): return "🏐"
    if any(x in t for x in ["badminton", "bwf", "cau long", "wenyu", "ginting", "jonatan"]): return "🏸"
    if any(x in t for x in ["tennis", "quan vot"]): return "🎾"
    if any(x in t for x in ["futsal"]): return "🏟️"
    if any(x in t for x in ["gp", "f1", "race", "dua xe", "moto"]): return "🏎️"
    return "⚽"

def resolve_asset_url(category, assets_list):
    cat_norm = category.lower().replace(" ", "_")
    filename = f"{cat_norm}.png"
    if filename in assets_list: return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/logos/{filename}"
    if any(k in cat_norm for k in ["football", "presiden", "asean", "focus"]):
        if "football.png" in assets_list: return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/logos/football.png"
    return DEFAULT_ASSET

def check_entry_validity(m_time, m_date, now):
    """Loloskan semua laga yang muncul di halaman depan (v16.5 - Hybrid)."""
    if m_time == "LIVE": return True
    try:
        # v16.5: Abaikan filter tanggal yang kaku karena website sering telat update tanggal URL
        # Kita percayakan pada website: jika tampil di halaman depan, berarti valid
        return True
    except: return True

async def fetch_registry_state():
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
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/logos"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    try:
        r = requests.get(api_url, headers=headers)
        if r.status_code == 200: return [file["name"].lower() for file in r.json() if file["name"].endswith(".png")]
    except: pass
    return []

def commit_to_storage(content):
    if not GITHUB_TOKEN: return False
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{MANIFEST_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    for attempt in range(GITHUB_RETRY_LIMIT):
        try:
            r = requests.get(api_url, headers=headers)
            sha = r.json().get("sha") if r.status_code == 200 else None
            payload = {"message": f"System Registry Sync {datetime.now().strftime('%Y-%m-%d %H:%M')}", "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")}
            if sha: payload["sha"] = sha
            res = requests.put(api_url, headers=headers, json=payload)
            if res.status_code in [200, 201]: return True
            elif res.status_code == 409: import time; time.sleep(random.uniform(1, 3))
        except: break
    return False

def finalize_sync(registry):
    """Menyimpan data (v16.5: Loloskan Semua Jadwal Hari Ini)."""
    now = get_now_wib()
    final_list = []

    for x in registry.values():
        if x.get("id", "").startswith("sys_v6"):
            final_list.append(x); continue

        # v16.5: Masukkan semua tanpa filter jam yang rumit agar tab event tidak kosong
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
        print(f"    [SNIPER] {len(final_list)} verified entries synced.")
    except Exception as e: print(f"    [!] Gagal simpan lokal: {e}")
    commit_to_storage(content)

async def process_entry_manifest(context, info, registry, semaphore):
    m_url = info["url"]; m_id = info["id"]; m_title = info.get("title", "Unknown")
    async with semaphore:
        print(f"    [>>>] Menyerbu Link: {m_title}...")
        page = await context.new_page()
        try: await Stealth().apply_stealth_async(page)
        except: pass
        links = []; uri = ""; headers = {}
        async def sniffer(request):
            url = request.url
            if any(kw in url.lower() for kw in [".m3u8", ".mpd", ".flv"]) and not url.startswith("blob:"):
                prio = 300 if ".m3u8" in url.lower() else 100
                if any(dom in url.lower() for dom in ["cdn", "streamby", "live", "manifest"]): prio += 100
                links.append({"url": url, "headers": dict(request.headers), "priority": prio})
        page.on("request", sniffer)
        try:
            await page.goto(m_url, wait_until="domcontentloaded", timeout=30000)
            await page.mouse.wheel(0, 400); await asyncio.sleep(1); await page.mouse.wheel(0, -400)
            for i in range(HUNTING_TIMEOUT):
                if links:
                    best = sorted(links, key=lambda x: x['priority'], reverse=True)[0]
                    if ".m3u8" in best["url"].lower():
                        uri = best["url"]; headers = best["headers"]; break
                if i == 2 or i == 8:
                    for frame in page.frames:
                        for s in ["button.vjs-big-play-button", ".play-icon", "text=Play", "text=HLS"]:
                            try:
                                btn = await frame.query_selector(s)
                                if btn: await btn.click()
                            except: pass
                await asyncio.sleep(1)
            if not uri:
                js_uri = await page.evaluate("() => { const v = document.querySelector('video'); return (v && v.src && !v.src.includes('blob')) ? v.src : null; }")
                if js_uri: uri = js_uri
            if uri:
                registry[m_id]["uri"] = f"{uri}{'&' if '?' in uri else '?'}sys_cache={int(datetime.now().timestamp())}"
                registry[m_id]["is_live"] = True
                registry[m_id]["headers"] = headers
                print(f"    [BERHASIL] Link didapat!")
                return True
        except: pass
        finally: await page.close()
        print(f"    [ZONK] Gagal.")
        return False

async def run_sync_cycle():
    if not os.path.exists(SESSION_DIR): os.makedirs(SESSION_DIR)
    now = get_now_wib()
    print(f"[SYSTEM] Memulai Siklus Sinkronisasi (V16.3) - WIB: {now.strftime('%H:%M')}...")
    state = await fetch_registry_state()
    registry = {}
    for entry in FIXED_ENTRIES: registry[entry["id"]] = entry
    assets = get_remote_assets()
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=HEADLESS_MODE)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36", ignore_https_errors=True)
        except: return
        queue = []
        for endpoint in ENDPOINTS:
            page = await context.new_page()
            try: await Stealth().apply_stealth_async(page)
            except: pass
            try:
                print(f"[*] Memindai: {endpoint}...")
                await page.goto(endpoint, wait_until="load", timeout=60000)
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(5)
                nodes = []
                for _ in range(3):
                    try:
                        nodes = await page.query_selector_all("a[href*='truc-tiep']")
                        if nodes: break
                    except: await asyncio.sleep(2)
                print(f"    [OK] Ditemukan {len(nodes)} link di {endpoint}.")
                seen = set()
                for node in nodes:
                    try:
                        href = await node.get_attribute("href")
                        if not href: continue
                        full_url = href if href.startswith("http") else endpoint.rstrip("/") + "/" + href.lstrip("/")
                        slug = full_url.strip("/").split("/")[-1]
                        if not slug or slug in seen or slug.isdigit(): continue
                        seen.add(slug)
                        label, m_time, m_date = parse_registry_slug(slug)
                        raw_text = await node.inner_text()
                        if not raw_text:
                            par = await node.query_selector("xpath=ancestor::div[1]")
                            raw_text = await par.inner_text() if par else ""
                        ctx = remove_accents(f"{label} {raw_text} {slug}")
                        if not check_entry_validity(m_time, m_date, now): continue
                        if any(k in ctx for k in BLOCK_LIST): continue
                        m_id = f"sys_{m_date}_{slug.replace('-', '_').split('_luc_')[0]}"
                        is_due = False
                        if m_time == "LIVE": is_due = True
                        else:
                            try:
                                t_obj = datetime.strptime(m_time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
                                if m_date and int(m_date[:2]) > now.day: t_obj += timedelta(days=1)
                                if now >= (t_obj - timedelta(minutes=15)): is_due = True
                            except: pass
                        if m_id not in registry:
                            cat = "FOOTBALL"
                            if any(k in ctx for k in ["presiden", "president"]): cat = "PIALA PRESIDEN"
                            elif any(k in ctx for k in ["badminton", "cau long", "tennis"]): cat = "SPORTS"
                            elif any(k in ctx for k in ["asean", "aff", "indonesia"]): cat = "ASEAN FOOTBALL"
                            elif any(k in ctx for k in ["malaysia", "sabah", "jdt"]): cat = "MALAYSIA FOOTBALL"
                            existing_uri = ""; existing_headers = {}
                            if m_id in state and state[m_id].get("uri"):
                                existing_uri = state[m_id]["uri"]; existing_headers = state[m_id].get("headers", {})
                            registry[m_id] = {
                                "id": m_id, "title": f"{get_entry_icon(label)} {label}",
                                "category": cat, "uri": existing_uri, "is_live": False,
                                "match_time": m_time, "headers": existing_headers,
                                "drm_info": {"is_protected": False, "drm_type": "", "drm_key": ""},
                                "epg_metadata": {"tvg_id": m_id, "tvg_name": label, "tvg_logo": resolve_asset_url(cat, assets), "source_xml": "Embedded"}
                            }
                            if is_due and not existing_uri:
                                queue.append({"id": m_id, "url": full_url, "title": label, "time": m_time})
                    except: continue
            except Exception as e: print(f"[!] Radar Gagal: {e}")
            finally: await page.close()
        if queue:
            print(f"[CORE] Menyerbu {len(queue)} laga LIVE secara PARALEL...")
            semaphore = asyncio.Semaphore(MAX_CONCURRENT_TABS)
            async def safe_hunter(item):
                try:
                    if await process_entry_manifest(context, item, registry, semaphore): finalize_sync(registry)
                except: pass
            await asyncio.gather(*(safe_hunter(item) for item in queue), return_exceptions=True)
        finalize_sync(registry)
        await browser.close()
        print(f"[SYSTEM] Cycle complete.\n")

async def main():
    if IS_CLOUD: await run_sync_cycle()
    else:
        while True:
            await run_sync_cycle()
            await asyncio.sleep(60)

if __name__ == "__main__": asyncio.run(main())
