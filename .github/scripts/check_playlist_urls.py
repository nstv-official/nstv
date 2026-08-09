#!/usr/bin/env python3
import csv
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

path = Path(sys.argv[1] if len(sys.argv) > 1 else "system_config_v3.data")
data = json.loads(path.read_text(encoding="utf-8"))

targets = {}
for i, item in enumerate(data, 1):
    uri = item.get("uri", "")
    if uri and uri not in targets:
        headers = dict(item.get("headers") or {})
        if item.get("user_agent"):
            headers["User-Agent"] = item["user_agent"]
        targets[uri] = {"headers": headers}

def check(uri, meta):
    headers = dict(meta["headers"])
    headers["Accept"] = "*/*"
    try:
        r = requests.get(uri, headers=headers, timeout=(8, 15), allow_redirects=True, stream=True)
        status = r.status_code
        final_url = r.url
        r.close()
        if 200 <= status < 400:
            state = "alive"
        elif status in (401, 403):
            state = "blocked"
        elif status in (404, 410):
            state = "dead"
        elif 500 <= status < 600:
            state = "server_error"
        else:
            state = "other"
        return state, status, final_url, ""
    except requests.exceptions.Timeout as e:
        return "timeout", "", "", str(e)
    except requests.exceptions.RequestException as e:
        return "unreachable", "", "", str(e)

results = {}
with ThreadPoolExecutor(max_workers=24) as pool:
    futures = {pool.submit(check, u, m): u for u, m in targets.items()}
    for fut in as_completed(futures):
        u = futures[fut]
        try:
            results[u] = fut.result()
        except Exception as e:
            results[u] = ("error", "", "", str(e))

rows = []
dead = []
for i, item in enumerate(data, 1):
    uri = item.get("uri", "")
    state, status, final_url, error = results.get(uri, ("missing", "", "", ""))
    row = {
        "id": item.get("id", str(i)),
        "category": item.get("category", ""),
        "title": item.get("title", ""),
        "uri": uri,
        "status": state,
        "http_status": status,
        "final_url": final_url,
        "error": error,
    }
    rows.append(row)
    if state == "dead":
        dead.append(row)

with open("playlist_url_audit.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)

Path("playlist_url_audit.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
with open("playlist_dead_channels.txt", "w", encoding="utf-8") as f:
    for row in dead:
        f.write(f'{row["id"]}\t{row["title"]}\t{row["http_status"]}\t{row["uri"]}\n')

counts = {}
for row in rows:
    counts[row["status"]] = counts.get(row["status"], 0) + 1
print("URL audit:", counts)
print("Dead channels:", len(dead))
