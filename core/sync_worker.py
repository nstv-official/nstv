import asyncio
import json
import re
import base64
import requests
import os
import random
from datetime import datetime, timedelta
from playwright.async_api import async_playwright
import playwright_stealth

# ==============================================================================
# SYSTEM CONFIGURATION (V14.6 - DATA SANITIZATION & DATE AWARE)
# ==============================================================================
# Security: Using environment secrets for data authentication (v14.3)
GITHUB_TOKEN = os.getenv("GH_TOKEN")
REPO_OWNER = "nstv-official"
REPO_NAME = "nstv"
MANIFEST_PATH = "manifest_v4.json"

# Environment Detection
IS_CLOUD = os.getenv("GITHUB_ACTIONS") == "true"
HEADLESS_MODE = True

# Path Management (OS Adaptive)
if IS_CLOUD:
    SESSION_DIR = "./internal_cache"
    LOG_DIR = "./system_logs"
else:
    SESSION_DIR = r"D:\NSTV_Internal_Cache"
    LOG_DIR = r"D:\NSTV_System_Logs"

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
PRIORITY_GROUPS = ["Presiden", "President", "Asean", "AFF", "Hyundai", "U19", "U23", "V-League", "Liga 1", "Champions"]
BLOCK_LIST = ["lol", "esports", "lck", "lpl", "gen g", "t1", "dota", "gaming", "valorant", "pubg", "mlbb", "pga"]
ENDPOINTS = ["https://xoilaczzggz.tv", "https://xoilacxtu.tv"]
DEFAULT_ASSET = "https://raw.githubusercontent.com/nstv-official/nstv/main/logos/default_logo.png"
# ==============================================================================

def clean_text_data(input_str):
    s1 = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"
    s0 = "aaaaaaaaaaaaaaaaaeeeeeeeeeeeiiiiiooooooooooooooooouuuuuuuuuuuyyyyyd"
    result = input_str.lower()
    for i in range(len(s1)): result = result.replace(s1[i], s0[i])
    return result

def parse_registry_slug(slug):
    """Mengekstrak nama tim, jam, dan tanggal dari URL slug (v14.6)."""
    slug_clean = slug.strip("/").split("/")[-1]

    # 1. Cari Waktu: luc-1530
    time_match = re.search(r'luc-(\d{2})(\d{2})', slug_clean)
    m_time = f"{time_match.group(1)}:{time_match.group(2)}" if time_match else "LIVE"

    # 2. Cari Tanggal: ngay-28-07-2026
    date_match = re.search(r'ngay-(\d{2})-(\d{2})-(\d{4})', slug_clean)
    m_date = f"{date_match.group(1)}-{date_match.group(2)}-{date_match.group(3)}" if date_match else ""

    # 3. Bersihkan Nama Tim
    team_part = slug_clean.split("-luc-")[0]
    # Transformasi Cerdas
    clean_label = team_part.replace("-vs-", " VS ").replace("-", " ")

    # Perbaikan Nama Khusus & Singkatan (v14.6)
    replacements = {
        r"\bnu\b": "Women",
        r"\bopmm\b": "DPMM",
        r"\bfc\b": "FC",
        r"\bpsm\b": "PSM",
        r"\barema\b": "AREMA",
        r"\bu(\d+)\b": r"U-\1",
        r"\baff\b": "AFF",
        r"\bbwf\b": "BWF"
    }
    for pattern, repl in replacements.items():
        clean_label = re.sub(pattern, repl, clean_label, flags=re.IGNORECASE)

    return clean_label.title(), m_time, m_date

def resolve_asset_url(category, assets_list):
    cat_norm = category.lower().replace(" ", "_")
    filename = f"{cat_norm}.png"
    if filename in assets_list:
        return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/logos/{filename}"

    # Fallback ke football.png untuk semua yang berbau bola
    if any(k in cat_norm for k in ["football", "presiden", "asean", "focus", "data_stream"]):
        if "football.png" in assets_list:
            return f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/main/logos/football.png"

    return DEFAULT_ASSET

def get_entry_icon(label):
    t = label.lower()
    if any(x in t for x in ["voli", "volleyball"]): return "🏐"
    if any(x in t for x in ["badminton", "bwf"]): return "🏸"
    return "⚽"

def check_entry_validity(m_time, m_date, now):
    """Validasi tanggal dan waktu agar tidak menampilkan laga basi (v14.6)."""
    if m_time == "LIVE": return True

    try:
        # Cek Tanggal jika ada (Format: dd-mm-yyyy)
        if m_date:
            m_date_obj = datetime.strptime(m_date, "%d-%m-%Y")
            # Hanya ijinkan hari ini atau besok dini hari (untuk laga malam)
            if m_date_obj.date() < now.date(): return False
            if m_date_obj.date() > now.date() + timedelta(days=1): return False

        # Cek Jam
        m_time_obj = datetime.strptime(m_time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
        # Jika tanggal besok, sesuaikan m_time_obj
        if m_date and datetime.strptime(m_date, "%d-%m-%Y").date() > now.date():
            m_time_obj += timedelta(days=1)

        # Tampilkan jika: 2 jam lalu s/d 12 jam ke depan
        return now - timedelta(hours=2) <= m_time_obj <= now + timedelta(hours=12)
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
    api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{MANIFEST_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    try:
        r = requests.get(api_url, headers=headers)
        sha = r.json().get("sha") if r.status_code == 200 else None
        payload = {"message": f"System Sync {datetime.now().strftime('%Y-%m-%d %H:%M')}", "content": base64.b64encode(content.encode("utf-8")).decode("utf-8")}
        if sha: payload["sha"] = sha
        res = requests.put(api_url, headers=headers, json=payload)
        if res.status_code in [200, 201]: print(f"    [CORE] Data committed successfully.")
    except: pass

def finalize_sync(registry):
    final_list = list(registry.values())
    def sort_logic(x):
        is_fixed = 0 if x.get("id", "").startswith("sys_") else 1
        is_live_prio = 0 if x.get("is_live") else 1
        cat = x.get("category", "").upper()
        prio_cat = 0 if "PRESIDEN" in cat else (1 if "ASEAN" in cat else 2)
        return (is_fixed, prio_cat, is_live_prio, x.get("match_time", "99:99"))
    final_list.sort(key=sort_logic)
    content = json.dumps(final_list, indent=4)
    commit_to_storage(content)

async def process_entry_manifest(context, info, registry):
    m_url = info["url"]; m_id = info["id"]
    page = await context.new_page()
    playwright_stealth.stealth(page)
    links = []; uri = ""; headers = {}

    async def sniffer(request):
        url = request.url
        if any(kw in url.lower() for kw in [".m3u8", ".mpd", ".flv"]) and not url.startswith("blob:"):
            prio = 300 if ".m3u8" in url.lower() else 100
            links.append({"url": url, "headers": dict(request.headers), "priority": prio})

    page.on("request", sniffer)
    try:
        await page.goto(m_url, wait_until="domcontentloaded", timeout=25000)
        for i in range(12):
            if links:
                best = sorted(links, key=lambda x: x['priority'], reverse=True)[0]
                if ".m3u8" in best["url"].lower():
                    uri = best["url"]; headers = best["headers"]
                    break
            if i == 2:
                for s in ["button.vjs-big-play-button", ".play-icon", "text=Play"]:
                    try:
                        btn = await page.query_selector(s)
                        if btn: await btn.click()
                    except: pass
            await asyncio.sleep(1)
        if not uri:
            js = await page.evaluate("() => { const v = document.querySelector('video'); return (v && v.src && !v.src.includes('blob')) ? v.src : null; }")
            if js: uri = js
        if uri:
            registry[m_id]["uri"] = f"{uri}{'&' if '?' in uri else '?'}sys_cache={int(datetime.now().timestamp())}"
            registry[m_id]["is_live"] = True
            registry[m_id]["headers"] = headers
            return True
    except: pass
    finally: await page.close()
    return False

async def run_sync_cycle():
    if not os.path.exists(SESSION_DIR): os.makedirs(SESSION_DIR)

    state = await fetch_registry_state()
    registry = {}
    for entry in FIXED_ENTRIES: registry[entry["id"]] = entry
    assets = get_remote_assets()

    async with async_playwright() as p:
        print(f"[SYSTEM] Initializing Sync Cycle (V14.1)...")
        try:
            browser = await p.chromium.launch(headless=HEADLESS_MODE)
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = await context.new_page()
            playwright_stealth.stealth(page)
        except: return

        now = datetime.now()
        queue = []

        for endpoint in ENDPOINTS:
            try:
                await page.goto(endpoint, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(8)
                nodes = await page.query_selector_all("a[href*='truc-tiep']")
                seen = set()

                for node in nodes:
                    try:
                        href = await node.get_attribute("href")
                        if not href: continue
                        full_url = href if href.startswith("http") else endpoint.rstrip("/") + "/" + href.lstrip("/")
                        slug = full_url.strip("/").split("/")[-1]
                        if not slug or slug in seen or any(k in slug.lower() for k in BLOCK_LIST): continue
                        seen.add(slug)

                        label, m_time, m_date = parse_registry_slug(slug)
                        raw_text = await node.inner_text()
                        if not raw_text:
                            par = await node.query_selector("xpath=ancestor::div[1]")
                            raw_text = await par.inner_text() if par else ""

                        ctx = clean_text_data(f"{label} {raw_text} {slug}")
                        if not check_entry_validity(m_time, m_date, now): continue

                        m_id = f"sys_{slug.replace('-', '_').split('_luc_')[0]}"

                        is_live = False
                        if m_time == "LIVE":
                            is_live = True
                        else:
                            try:
                                t_obj = datetime.strptime(m_time, "%H:%M").replace(year=now.year, month=now.month, day=now.day)
                                if m_date and datetime.strptime(m_date, "%d-%m-%Y").date() > now.date():
                                    t_obj += timedelta(days=1)

                                # LIVE hanya jika jam sudah lewat DAN maksimal 2.5 jam berlalu
                                if now >= t_obj and now <= t_obj + timedelta(minutes=150):
                                    is_live = True
                            except: pass

                        if m_id not in registry:
                            cat = "DATA_STREAM"
                            if "presiden" in ctx: cat = "PIALA PRESIDEN"
                            elif any(k in ctx for k in ["asean", "aff", "indonesia"]): cat = "ASEAN FOOTBALL"

                            existing_uri = ""; existing_headers = {}
                            if m_id in state and state[m_id].get("uri"):
                                existing_uri = state[m_id]["uri"]
                                existing_headers = state[m_id].get("headers", {})

                            registry[m_id] = {
                                "id": m_id, "title": f"{get_entry_icon(ctx)} {label}",
                                "category": cat, "uri": existing_uri, "is_live": is_live,
                                "match_time": m_time, "headers": existing_headers,
                                "drm_info": {"is_protected": False, "drm_type": "", "drm_key": ""},
                                "epg_metadata": {"tvg_id": m_id, "tvg_name": label, "tvg_logo": resolve_asset_url(cat, assets), "source_xml": "Embedded"}
                            }
                            if is_live and not existing_uri:
                                queue.append({"id": m_id, "url": full_url, "title": label})
                    except: continue
            except: pass

        if queue:
            print(f"[CORE] Processing {len(queue[:10])} entries...")
            for item in queue[:10]:
                if await process_entry_manifest(context, item, registry):
                    finalize_sync(registry)

        finalize_sync(registry)
        await browser.close()
        print(f"[SYSTEM] Cycle complete.")

async def main():
    if IS_CLOUD:
        await run_sync_cycle()
    else:
        while True:
            await run_sync_cycle()
            await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
