#!/usr/bin/env python3
import json
import sys
from pathlib import Path

path = Path(sys.argv[1] if len(sys.argv) > 1 else "system_config_v3.data")
data = json.loads(path.read_text(encoding="utf-8"))
for i, item in enumerate(data, 1):
    item["id"] = str(i)
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Renumbered {len(data)} channels: IDs 1..{len(data)}")
