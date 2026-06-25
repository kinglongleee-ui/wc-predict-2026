#!/usr/bin/env python3
"""translate_all_zh.py — 一次性翻译所有 run 的英文 narrative 字段为中文."""
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

# 找出需要翻译的 run (prediction 含英文)
to_translate = []
for fp in sorted((ROOT / "data/runs").glob("run_*.json")):
    d = json.loads(fp.read_text())
    v = d.get("verdict", {})
    p = v.get("prediction", "")
    if p and sum(1 for c in p[:300] if ord(c) > 127) < 100:  # 英文为主
        to_translate.append((fp, d, v, p))

print(f"Found {len(to_translate)} runs to translate")

# 一次性 batch 翻译
def translate(text: str) -> str:
    if not text or sum(1 for c in text[:200] if ord(c) > 127) > 100:
        return text  # 已中文
    resp = requests.post(
        f"{BASE}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
        json={
            "model": MODEL,
            "messages": [
                {"role": "system", "content": "你是中英翻译专家, 把足球预测 narrative 翻译成流畅的中文, 保留数字、队名、人名、百分比。"},
                {"role": "user", "content": f"翻译为中文:\n\n{text[:2000]}"},
            ],
            "temperature": 0.3,
            "max_tokens": 2000,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

for fp, d, v, p in to_translate:
    print(f"\n=== Translating {fp.stem} ===")
    print(f"  pred: {p[:100]}...")
    try:
        # 翻译 prediction
        new_pred = translate(p)
        v["prediction"] = new_pred
        print(f"  → ZH: {new_pred[:100]}...")

        # 翻译 key_dynamics
        new_kd = []
        for kd in v.get("key_dynamics", []):
            if isinstance(kd, str) and sum(1 for c in kd[:200] if ord(c) > 127) < 100:
                new_kd.append(translate(kd))
            else:
                new_kd.append(kd)
        v["key_dynamics"] = new_kd

        # 翻译 signals
        for sig in v.get("signals", []):
            s_text = sig.get("signal", "")
            if isinstance(s_text, str) and sum(1 for c in s_text[:200] if ord(c) > 127) < 100:
                sig["signal"] = translate(s_text)

        # 翻译 upset_risks
        for ur in d.get("upset_risks", []):
            r = ur.get("reason", "")
            if isinstance(r, str) and sum(1 for c in r[:200] if ord(c) > 127) < 100:
                ur["reason"] = translate(r)

        # 翻译 best_thirds
        for bt in d.get("best_thirds", []):
            r = bt.get("reason", "")
            if isinstance(r, str) and sum(1 for c in r[:200] if ord(c) > 127) < 100:
                bt["reason"] = translate(r)

        # 保存
        fp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  ✓ saved {fp.name}")
    except Exception as e:
        print(f"  ✗ error: {e}")

print(f"\n✓ Done")
