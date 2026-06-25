#!/usr/bin/env python3
"""translate_zh_fast.py — 直接 inline 翻译, no M3 thinking, 串行快速版."""
import json, os
from pathlib import Path
import requests

ROOT = Path("/home/king/wc-predict")

# 读 .env
for env_path in (ROOT / ".env.local", Path("/home/king/mirofish-cli/.env")):
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("LLM_API_KEY="):
                os.environ.setdefault("LLM_API_KEY", line.split("=", 1)[1].strip())
            if line.startswith("LLM_BASE_URL="):
                os.environ.setdefault("LLM_BASE_URL", line.split("=", 1)[1].strip())
            if line.startswith("LLM_MODEL_NAME="):
                os.environ.setdefault("LLM_MODEL_NAME", line.split("=", 1)[1].strip())

API_KEY = os.environ.get("LLM_API_KEY")
BASE = os.environ.get("LLM_BASE_URL", "https://api.minimaxi.com/v1")
MODEL = os.environ.get("LLM_MODEL_NAME", "MiniMax-M3")

def translate(text: str) -> str:
    if not text or sum(1 for c in text[:200] if ord(c) > 127) > 80:
        return text
    # Use temp=0 + max_tokens 适当 + 严格 system prompt 禁 thinking
    resp = requests.post(
        f"{BASE}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "翻译:把英文翻译成中文。直接输出译文, 没有任何前缀解释, 没有任何标签。保留数字、人名、队名、百分比。"},
                {"role": "user", "content": text[:1500]},
            ],
            "temperature": 0.0,
            "max_tokens": 1500,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

# 处理 6 个 run
TARGETS = ["3e9d8be4115d", "d1f74f4afe69", "905a0881175d", "a18431af48fd", "b37f734df790", "ea1419a0e22f"]
for run_id in TARGETS:
    fp = ROOT / f"data/runs/run_{run_id}.json"
    if not fp.exists():
        continue
    d = json.loads(fp.read_text())
    v = d.get("verdict", {})
    p = v.get("prediction", "")
    if not p or sum(1 for c in p[:200] if ord(c) > 127) > 80:
        print(f"✓ {run_id} already ZH")
        continue
    print(f"Translating {run_id}...")
    try:
        new_p = translate(p)
        v["prediction"] = new_p
        print(f"  pred: {new_p[:80]}...")

        # key_dynamics
        new_kd = []
        for kd in v.get("key_dynamics", []):
            if isinstance(kd, str):
                new_kd.append(translate(kd))
            else:
                new_kd.append(kd)
        v["key_dynamics"] = new_kd

        # signals
        for sig in v.get("signals", []):
            s = sig.get("signal", "")
            if isinstance(s, str):
                sig["signal"] = translate(s)

        # upset_risks
        for ur in d.get("upset_risks", []):
            r = ur.get("reason", "")
            if isinstance(r, str):
                ur["reason"] = translate(r)

        # best_thirds
        for bt in d.get("best_thirds", []):
            r = bt.get("reason", "")
            if isinstance(r, str):
                bt["reason"] = translate(r)

        fp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ saved {fp.name}")
    except Exception as e:
        print(f"  ✗ error: {e}")
