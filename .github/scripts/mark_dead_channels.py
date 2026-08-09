#!/usr/bin/env python3
import json
from pathlib import Path

playlist_path = Path("system_config_v3.data")
audit_path = Path("playlist_url_audit.json")
data = json.loads(playlist_path.read_text(encoding="utf-8"))
audit = json.loads(audit_path.read_text(encoding="utf-8"))

dead_ids = {str(row["id"]) for row in audit if row.get("status") == "dead"}
for item in data:
    title = str(item.get("title", ""))
    if title.startswith("[URL MATI] "):
        title = title[len("[URL MATI] "):]
    item["title"] = ("[URL MATI] " + title) if str(item.get("id")) in dead_ids else title

playlist_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Marked {len(dead_ids)} dead channels: {', '.join(sorted(dead_ids, key=int))}")
