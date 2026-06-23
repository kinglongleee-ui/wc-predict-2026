#!/usr/bin/env python3
"""用 MiniMax M3 一次性给 R6 全 73 场写 4 段梅花易数解读。

输入: data/meihua/run_<id>_meihua.json (qi_gua 已算出卦象/Top3 比分)
输出: 同文件, 增补 llm_narrative 字段, 每场含 4 段中文 markdown 文本。

约束:
- 一次性 prompt, 73 场; M3 用长上下文, 避免 73 次调用
- 失败回退到 meihua_qigua._render_basic/_render_interpretation/_render_score_hint/_render_reality_check
- 输出按场地标 [Match #1] ... [Match #73], 解析按 anchor 切
"""
from __future__ import annotations
import json
import os
import re
import sys
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))


MINIMAX_API = "https://api.minimaxi.com/v1/text/chatcompletion_v2"
MINIMAX_MODEL = "MiniMax-Text-01"
MINIMAX_KEY = os.environ.get("MINIMAX_API_KEY", "")


def _build_prompt(matches: list) -> str:
    """生成发给 M3 的 prompt: 73 场卦象 + Top3 比分 → 4 段解读。

    模板 (用户固定 4 段):
    [Match #1] <team_a> vs <team_b>
    【基础信息】开赛 UTC: ... 上卦 ... 下卦 ... 动爻 ... 本卦 ... 五行
    【卦象解读】本卦 + 互卦 + 变卦 + 五行生克
    【卦数附会】Top3 比分 + 仅娱乐
    【客观现实】实力 + 战意 + 理性提醒
    """
    head = (
        "你是中国传统文化研习者, 专精《周易》梅花易数。请按以下 4 段固定模板, "
        "为每场世界杯比赛写 100-200 字解读。\n\n"
        "【基础信息】开赛 UTC + 上卦(年+月+日 mod 8) + 下卦(+时 mod 8) + 动爻(mod 6) + 本卦名 + 五行\n"
        "【卦象解读】本卦本义 + 互卦走势 + 变卦末段 + 五行生克旺衰\n"
        "【卦数附会】卦数附会比分 + 必标'仅娱乐'\n"
        "【客观现实】实力对比 + 战意 + 理性提醒(切勿投注)\n\n"
        "起卦公式: 上卦=(年+月+日) mod 8 (0=坤), 下卦=(年+月+日+时) mod 8, 动爻=(年+月+日+时) mod 6 (0=6爻)。\n"
        "五行: 乾兑金, 离火, 震巽木, 坎水, 艮坤土。\n"
        "体用: 动爻 1-3 在上卦 → 下卦为体(主队); 动爻 4-6 在下卦 → 上卦为体(主队)。\n\n"
        "--- 73 场比赛卦象 + Top3 比分 ---\n\n"
    )
    body_lines = []
    for i, m in enumerate(matches, 1):
        qg = m.get('meihua') or {}
        if not qg:
            body_lines.append(f"[Match #{i}] {m.get('team_a')} vs {m.get('team_b')} (无卦象, 跳过)")
            continue
        score_str = ", ".join(
            f"{s['home']}:{s['away']}({s['pct']:.0f}%)"
            for s in qg.get('top_3_scores', [])[:3]
        )
        body_lines.append(
            f"[Match #{i}] {m.get('team_a')} vs {m.get('team_b')}\n"
            f"  开赛 UTC: {qg.get('kickoff_utc')}\n"
            f"  上卦: {qg.get('trigram_upper')} ({qg.get('host_element') if qg.get('host_trigram') == qg.get('trigram_upper') else qg.get('guest_element')})\n"
            f"  下卦: {qg.get('trigram_lower')}\n"
            f"  动爻: 第 {qg.get('changing_line')} 爻\n"
            f"  本卦: {qg.get('trigram_upper')}上{qg.get('trigram_lower')}下\n"
            f"  体: {qg.get('host_trigram')}(主队) 用: {qg.get('guest_trigram')}(客队)\n"
            f"  五行关系: {qg.get('five_element_relation')}\n"
            f"  Top3 比分: {score_str}\n"
            f"  预测胜方: {qg.get('predicted_winner') or '平局'}\n"
        )
    foot = (
        "\n--- 输出格式 ---\n"
        "请按 73 个 [Match #N] 段落输出, 每段严格 4 个【】块, 不要任何开场白或结束语。\n"
        "中文, 每段 100-200 字。Top3 比分保留。理性提醒段必须含'梅花易数仅游戏, 切勿投注'。\n"
        "Match 之间空一行。"
    )
    return head + "\n".join(body_lines) + foot


def _call_minimax(prompt: str, timeout: int = 240) -> str:
    """调 MiniMax M3 chat completion, 返回 generated text."""
    if not MINIMAX_KEY:
        raise RuntimeError("MINIMAX_API_KEY not set")
    payload = json.dumps({
        "model": MINIMAX_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7,
        "max_tokens": 16000,
    }).encode("utf-8")
    req = urllib.request.Request(
        MINIMAX_API,
        data=payload,
        headers={
            "Authorization": f"Bearer {MINIMAX_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


_ANCHOR_RE = re.compile(r"\[Match\s*#(\d+)\]\s*(.+?)(?=\n|$)")


def _parse_llm_output(text: str, total: int) -> dict[int, str]:
    """按 [Match #N] 切分, 返回 {N: 4 段文本}。"""
    out = {}
    # 用 split 按 anchor 切, 第一个 split 之前是 preamble (丢掉)
    parts = _ANCHOR_RE.split(text)
    # parts 形如 [preamble, "1", "match text", "2", "match text", ...]
    if len(parts) < 3:
        return out
    # 从 index 1 起 (preamble 后): [num, body, num, body, ...]
    for i in range(1, len(parts) - 1, 2):
        num_str = parts[i].strip()
        try:
            n = int(num_str)
        except ValueError:
            continue
        body = parts[i + 1].strip()
        # 截断到下一个 [Match #] 之前 (已经按 anchor split 了, body 不含)
        out[n] = body
    return out


def main(run_id: str):
    meihua_path = ROOT / 'data' / 'meihua' / f'run_{run_id}_meihua.json'
    if not meihua_path.exists():
        sys.exit(f"❌ meihua file not found: {meihua_path}")
    data = json.loads(meihua_path.read_text(encoding='utf-8'))
    matches = data['matches']
    print(f"准备给 {len(matches)} 场写 4 段解读...")

    prompt = _build_prompt(matches)
    print(f"Prompt 长度: {len(prompt)} chars")

    try:
        text = _call_minimax(prompt)
        print(f"M3 返回: {len(text)} chars")
    except (urllib.error.URLError, RuntimeError, KeyError, json.JSONDecodeError) as e:
        print(f"⚠ M3 调用失败 ({type(e).__name__}: {e}), 回退到模板渲染")
        text = ""

    parsed = _parse_llm_output(text, len(matches)) if text else {}
    print(f"成功解析 {len(parsed)}/{len(matches)} 个 Match 段")

    # 把 LLM 文本合并进 meihua 字段, 没解析到的保留模板
    from meihua_qigua import (
        qi_gua,
        _render_basic,
        _render_interpretation,
        _render_score_hint,
        _render_reality_check,
        _element_of,
    )
    for i, m in enumerate(matches, 1):
        qg = m.get('meihua')
        if not qg:
            continue
        # 模板版 (作为 fallback)
        dt_utc = None
        from datetime import datetime
        try:
            dt_utc = datetime.strptime(qg['kickoff_utc'], "%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, KeyError):
            continue
        basic = _render_basic(qg['trigram_upper'], qg['trigram_lower'], qg['changing_line'], dt_utc)
        interp = _render_interpretation(
            qg['trigram_upper'], qg['trigram_lower'], qg['changing_line'],
            qg['host_trigram'], qg['guest_trigram'],
            qg['five_element_relation'], qg['host_element'], qg['guest_element'],
        )
        score = _render_score_hint(qg['top_3_scores'], qg['five_element_relation'], qg['predicted_winner'])
        reality = _render_reality_check(m['team_a'], m['team_b'])
        fallback = (
            f"【基础信息】\n{basic}\n\n"
            f"【卦象解读】\n{interp}\n\n"
            f"【卦数附会】\n{score}\n\n"
            f"【客观现实】\n{reality}"
        )
        llm_text = parsed.get(i, "")
        qg['llm_narrative'] = llm_text if llm_text else None
        qg['template_fallback'] = fallback  # 永远保留模板兜底

    # 写回
    meihua_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    llm_ok = sum(1 for m in matches if (m.get('meihua') or {}).get('llm_narrative'))
    print(f"✓ {llm_ok}/{len(matches)} 场有 LLM 文本 (其余走模板 fallback)")
    print(f"✓ 写回 {meihua_path}")


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(f"Usage: {sys.argv[0]} <run_id>")
    main(sys.argv[1])