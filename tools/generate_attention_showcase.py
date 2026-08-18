#!/usr/bin/env python3
import json
from pathlib import Path
from demo_generation.attention_showcase import generate_attention_showcase

ROOT=Path(__file__).resolve().parents[1]
def write(path,payload): path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
summary,details=generate_attention_showcase();base=ROOT/"data/demo/C-2308/attention";write(base/"weekly-summary.json",summary)
for week_id,detail in details.items(): write(base/"weeks"/f"{week_id}.json",detail)
print(f"Generated Attention V2: {len(summary['weeks'])} weeks, {sum(len(x['sessions']) for x in details.values())} sessions")
