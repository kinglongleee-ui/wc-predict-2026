#!/usr/bin/env python3
"""梅花易数 (Plum Blossom Numerology) 起卦引擎 — 邵雍时间起卦法。

输入: match datetime (UTC) + 两队名
输出: {
    trigram_upper: "乾", trigram_lower: "坤", changing_line: 3,
    host_trigram: "乾", guest_trigram: "坤",
    five_element_relation: "体克用" | "用克体" | "体生用" | "用生体" | "比和",
    base_score: {home: 2, away: 1},
    top_3_scores: [{home, away, prob, pct}, ...]
}

起卦法:
    上卦 = (年+月+日) % 8        # 8 卦 0=坤 1=震 2=坎 3=艮 4=离 5=兑 6=乾 7=巽
    下卦 = (年+月+日+时) % 8
    动爻 = (年+月+日+时) % 6      # 1-6
    体用: 动爻在上卦 (1-3) → 下卦为体; 动爻在下卦 (4-6) → 上卦为体

五行:
    乾/兑=金, 离=火, 震/巽=木, 坎=水, 艮/坤=土

生克:
    金克木, 木克土, 土克水, 水克火, 火克金 (克)
    金生水, 水生木, 木生火, 火生土, 土生金 (生)
"""
from __future__ import annotations
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Literal

# 起卦时区: 中国标准时间 (UTC+8). 用户 2026-06-22 明示要求按北京时间起卦
# (传统梅花易数邵雍法用的是本地时辰, 站点服务于中国用户, 统一按 CST)
CST = timezone(timedelta(hours=8))

# 8 卦 0-7: 后天八卦序 (坎坤震巽 离艮兑乾)
TRIGRAMS = ["坤", "震", "坎", "艮", "离", "兑", "乾", "巽"]
TRIGRAM_ELEMENT = {
    "乾": "金", "兑": "金",
    "离": "火",
    "震": "木", "巽": "木",
    "坎": "水",
    "艮": "土", "坤": "土",
}
ELEMENT_BIN = {"金": 0, "木": 1, "水": 2, "火": 3, "土": 4}

# 五行生克矩阵: 生(1) 克(-1) 同(0)
# rows = source (acting on), cols = target (acted upon)
# 生: 金→水, 水→木, 木→火, 火→土, 土→金
# 克: 金→木, 木→土, 土→水, 水→火, 火→金
SHENG_CYCLE = {"金": "水", "水": "木", "木": "火", "火": "土", "土": "金"}
KE_CYCLE = {"金": "木", "木": "土", "土": "水", "水": "火", "火": "金"}


def _trigram_index(remainder: int) -> str:
    """remainder ∈ [0,7] → 卦名."""
    return TRIGRAMS[remainder % 8]


def _element_of(trigram: str) -> str:
    return TRIGRAM_ELEMENT[trigram]


def _sheng_ke(host_el: str, guest_el: str) -> Literal["体生用", "用生体", "体克用", "用克体", "比和"]:
    """体=主队(host) 用=客队(guest)."""
    if host_el == guest_el:
        return "比和"
    if SHENG_CYCLE[host_el] == guest_el:
        return "体生用"   # host generates guest
    if SHENG_CYCLE[guest_el] == host_el:
        return "用生体"   # guest generates host
    if KE_CYCLE[host_el] == guest_el:
        return "体克用"   # host conquers guest
    if KE_CYCLE[guest_el] == host_el:
        return "用克体"   # guest conquers host
    return "比和"


def _base_score(trigram: str) -> int:
    """卦在地支数: 乾1 兑2 离3 震4 巽5 坎6 艮7 坤8; 映射到 1-3 进球基准。

    足球进球 0-4 常见, 用 1-3 作为基准更接近现实 (不会出现 0-0 过多)。
    """
    full = TRIGRAMS.index(trigram) + 1  # 1-8
    return max(1, min(3, 1 + (full - 1) // 3))   # 1-3→1, 4-6→2, 7-8→3


def _tiebreak(team_a: str, team_b: str) -> int:
    """同分时用队名 hash 加微小扰动 (prob 0.0001 级别), 保持 deterministic."""
    h = hashlib.sha256(f"{team_a}|{team_b}".encode("utf-8")).hexdigest()
    return int(h[:4], 16) % 100  # 0-99


def qi_gua(kickoff_utc: str | datetime, team_a: str, team_b: str) -> dict:
    """主入口: 给定开赛 UTC + 两队 → 返回完整卦象 + 比分。

    Args:
        kickoff_utc: ISO 字符串 (e.g. "2026-06-24T19:00Z") 或 datetime (UTC)
        team_a: 主队 (默认按 a 在前)
        team_b: 客队

    起卦时区: 中国标准时间 (UTC+8) — 邵雍时间起卦法用的是本地时辰,
    本站服务中国用户, 全部按北京时间起卦。
    """
    if isinstance(kickoff_utc, str):
        # 兼容 "2026-06-24T19:00Z" / "2026-06-24T19:00:00Z" / "+00:00"
        s = kickoff_utc.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
    else:
        dt = kickoff_utc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc)  # kickoff_utc_used 字段保留 UTC 原始时区
    dt_cst = dt.astimezone(CST)            # 起卦参数用北京时间

    # 梅花数 (年支序数): 用 (year - 3) % 60 (地支序) 太繁; 简化为公历年 + 月日
    # 邵雍原法: 上元 / 中元 / 下元 起始年不同; 简化用 (年+月+日+时) 干支数法
    # 用 CST (北京时间) 而非 UTC: 2026-06-22 起改, 用户明示要求
    y = dt_cst.year
    m = dt_cst.month
    d = dt_cst.day
    h = dt_cst.hour

    # 简化算法: 直接用 年月日时算术 mod
    upper_idx = (y + m + d) % 8
    lower_idx = (y + m + d + h) % 8
    changing_line = ((y + m + d + h) % 6) + 1  # 1-6

    upper = _trigram_index(upper_idx)
    lower = _trigram_index(lower_idx)

    # 体用: 动爻在 1-3 (上卦) → 下卦为体 (主队)
    #      动爻在 4-6 (下卦) → 上卦为体 (主队)
    if changing_line <= 3:
        host_trigram = lower   # 体
        guest_trigram = upper  # 用
    else:
        host_trigram = upper   # 体
        guest_trigram = lower  # 用

    host_el = _element_of(host_trigram)
    guest_el = _element_of(guest_trigram)
    relation = _sheng_ke(host_el, guest_el)

    # 比分推导
    base_home = _base_score(host_trigram)
    base_away = _base_score(guest_trigram)

    # 体用关系修正主队进球
    if relation == "体克用":     # 主队克制, 主队占优
        base_home += 1
    elif relation == "用克体":   # 客队反克, 主队被压
        base_home = max(0, base_home - 1)
        base_away += 1
    elif relation == "用生体":   # 客队生主队, 主队得力
        base_home += 1
    elif relation == "体生用":   # 主队泄力助客, 主队疲
        base_away += 1
    # 比和 → 不动

    # 动爻修正: 奇数爻 (1,3,5) 主队加势; 偶数 (2,4,6) 客队加势
    if changing_line % 2 == 1:
        base_home += 1
    else:
        base_away += 1

    # 裁剪到合理范围 0-4 (足球现实比分上限)
    base_home = max(0, min(4, base_home))
    base_away = max(0, min(4, base_away))

    # Top 3 比分 (中心分 + ±1)
    candidates = []
    for dh in (-1, 0, 1):
        for da in (-1, 0, 1):
            h = max(0, min(5, base_home + dh))
            a = max(0, min(5, base_away + da))
            candidates.append((h, a))
    # 去重保持顺序
    seen = set()
    uniq = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            uniq.append(c)

    # 概率: 中心 (base) 最高, 距离越远越低; 同距离按队名 hash 破平
    probs_raw = []
    for h, a in uniq:
        dh = abs(h - base_home)
        da = abs(a - base_away)
        dist = dh + da
        # 0→0.35, 1→0.27, 2→0.18 (中心加权)
        p = {0: 0.35, 1: 0.27, 2: 0.18}.get(dist, 0.05)
        probs_raw.append(((h, a), p))

    # 同 dist 破平: 用 tiebreak
    probs_raw.sort(key=lambda x: (-x[1], -_tiebreak(f"{team_a}|{x[0][0]}|{team_b}|{x[0][1]}", str(_tiebreak(team_a, team_b)))))

    # Top 3 按"中心最可能"排序, 概率固定分配 47% / 30% / 23% (再归一化)
    FIXED_PROBS = [0.47, 0.30, 0.23]
    top3 = probs_raw[:3]
    total = sum(FIXED_PROBS[:len(top3)]) or 1.0
    top3_scores = []
    for i, ((h, a), _) in enumerate(top3):
        p = FIXED_PROBS[i] if i < len(FIXED_PROBS) else (1.0 - total) / max(1, len(top3) - len(FIXED_PROBS))
        top3_scores.append({
            "home": h,
            "away": a,
            "prob": round(p / total, 4),
            "pct": round(p / total * 100, 1),
        })

    # 预测胜方
    if base_home > base_away:
        winner = "a"
    elif base_home < base_away:
        winner = "b"
    else:
        winner = None

    # 4 段模板: 基本信息 / 卦象解读 / 卦数附会 / 客观现实
    basic = _render_basic(upper, lower, changing_line, dt_cst)
    interp = _render_interpretation(upper, lower, changing_line, host_trigram, guest_trigram, relation, host_el, guest_el)
    score_hint = _render_score_hint(top3_scores, relation, winner)
    reality = _render_reality_check(team_a, team_b)

    return {
        "kickoff_utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trigram_upper": upper,
        "trigram_lower": lower,
        "changing_line": changing_line,
        "host_trigram": host_trigram,
        "guest_trigram": guest_trigram,
        "host_element": host_el,
        "guest_element": guest_el,
        "five_element_relation": relation,
        "base_score": {"home": base_home, "away": base_away},
        "top_3_scores": top3_scores,
        "predicted_winner": winner,
        # 4 段模板输出
        "basic": basic,
        "hexagram_interpretation": interp,
        "score_hint": score_hint,
        "reality_check": reality,
    }


# --- 4 段模板渲染 -------------------------------------------------------
# 八卦本义 (简表, 用于 interp 段本卦/互卦/变卦解读)
TRIGRAM_MEANING = {
    "乾": "天、为刚健、为进取",
    "兑": "泽、为悦、为口舌、为决断",
    "离": "火、为明、为礼、为燥",
    "震": "雷、为动、为惊、为突袭",
    "巽": "风、为顺、为入、为渗透",
    "坎": "水、为险、为陷、为暗流",
    "艮": "山、为止、为稳、为壁垒",
    "坤": "地、为顺、为承载、为防守",
}


def _render_basic(upper: str, lower: str, line: int, dt: datetime) -> str:
    """第 1 段: 比赛基础信息 (时间起卦参数 + 完整卦象)。

    格式参考用户模板: 上卦/下卦/动爻/本卦/互卦/变卦。
    dt 必须是 CST 时区 (qi_gua 已转).
    """
    # 上卦数 / 下卦数 (还原 mod 前的原始和, 给读者直观感知)
    y, m, d, h = dt.year, dt.month, dt.day, dt.hour
    upper_sum = y + m + d
    lower_sum = upper_sum + h
    return (
        f"开赛 北京时间: {dt.strftime('%Y-%m-%d %H:%M')} (CST, 辰位起卦)\n"
        f"上卦: 年+月+日={upper_sum} → 模 8 余 {(upper_sum - 1) % 8 + 1} → {upper} ({TRIGRAM_MEANING.get(upper, '')})\n"
        f"下卦: +时辰={lower_sum} → 模 8 余 {(lower_sum - 1) % 8 + 1} → {lower} ({TRIGRAM_MEANING.get(lower, '')})\n"
        f"动爻: 模 6 余 {((lower_sum - 1) % 6) + 1} → 第 {line} 爻动\n"
        f"本卦: {upper}上{lower}下 ({_hexagram_name(upper, lower)})\n"
        f"五行: 上{_element_of(upper)} / 下{_element_of(lower)}"
    )


# 64 卦本卦名 (简表 — 只覆盖上+下组合常见类象, 缺则用通用描述)
HEXAGRAM_NAMES = {
    ("乾", "乾"): "乾为天", ("坤", "坤"): "坤为地",
    ("坎", "乾"): "水天需", ("乾", "坎"): "天水讼",
    ("离", "坤"): "火地晋", ("坤", "离"): "地火明夷",
    ("震", "坤"): "雷地豫", ("坤", "震"): "地雷复",
    ("乾", "坤"): "天地否", ("坤", "乾"): "地天泰",
    ("艮", "乾"): "山天大畜", ("乾", "艮"): "天山遁",
    ("兑", "乾"): "泽天夬", ("乾", "兑"): "天泽履",
    ("震", "乾"): "雷天大壮", ("乾", "震"): "天雷无妄",
    ("巽", "乾"): "风天小畜", ("乾", "巽"): "天风姤",
    ("坎", "坤"): "水地比", ("坤", "坎"): "地水师",
    ("艮", "坤"): "山地剥", ("坤", "艮"): "地山谦",
    ("兑", "坤"): "泽地萃", ("坤", "兑"): "地泽临",
    ("巽", "坤"): "风地观", ("坤", "巽"): "地风升",
    ("离", "乾"): "火天大有", ("乾", "离"): "天火同人",
    ("震", "艮"): "雷山小过", ("艮", "震"): "山雷颐",
    ("巽", "兑"): "风泽中孚", ("兑", "巽"): "泽风大过",
    ("坎", "艮"): "水山蹇", ("艮", "坎"): "山水蒙",
    ("离", "兑"): "火泽睽", ("兑", "离"): "泽火革",
    ("震", "巽"): "雷风恒", ("巽", "震"): "风雷益",
    ("坎", "离"): "水火既济", ("离", "坎"): "火水未济",
    ("艮", "兑"): "山泽损", ("兑", "艮"): "泽山咸",
}


def _hexagram_name(upper: str, lower: str) -> str:
    return HEXAGRAM_NAMES.get((upper, lower), f"{upper}{lower}卦")


def _render_interpretation(upper: str, lower: str, line: int,
                            host_tri: str, guest_tri: str,
                            relation: str, host_el: str, guest_el: str) -> str:
    """第 2 段: 卦理解读 (本卦 + 互卦 + 变卦 + 五行生克)。

    体用定法: 上卦 = 用 (客队), 下卦 = 体 (主队) — 与模板一致。
    五行关系映射到优势判定:
      体克用/用生体 → 主队占优
      用克体/体生用 → 主队受制
      比和 → 拉锯
    """
    body_part = (
        f"本卦 {upper}{lower} ({_hexagram_name(upper, lower)}): "
        f"内{lower}为体(主队, {_element_of(lower)}), 外{upper}为用(客队, {_element_of(upper)}), "
        f"{_relation_phrase(relation)}。"
    )
    # 互卦: 取下卦初爻 + 中爻 = 下互; 上卦中爻 + 上爻 = 上互
    # 简化: 按 64 卦上下互易, 缺则描述五行流转
    hu_upper = lower   # 简化: 互卦上 = 下卦前两爻
    hu_lower = upper   # 互卦下 = 上卦后两爻 (示意)
    hu_part = (
        f"互卦: 互易得 {hu_upper}上{hu_lower}下 — "
        f"{_hu_phrase(hu_upper, hu_lower)}。"
    )
    # 变卦: 动爻所在卦改一爻 (简化: 用动爻奇偶代表主/客加势)
    bian_part = (
        f"变卦: 第 {line} 爻动 (奇数助体, 偶数助用) — "
        f"{_bian_phrase(line, relation)}。"
    )
    wuxing_part = (
        f"五行: {host_el} 主 {guest_el} 客, {relation}; "
        f"{_wuxing_month_phrase(host_el)}"
    )
    return " / ".join([body_part, hu_part, bian_part, wuxing_part])


def _relation_phrase(rel: str) -> str:
    return {
        "体克用": "体克用, 主队实力压制",
        "用克体": "用克体, 客队反压主队",
        "体生用": "体生用, 主队泄力助客",
        "用生体": "用生体, 客队反助主队, 主队得力",
        "比和": "体用比和, 五行同属, 拉锯战",
    }.get(rel, rel)


def _hu_phrase(upper: str, lower: str) -> str:
    return f"中后段 {_element_of(upper)} {_element_of(lower)} 相{_wuxing_interact(upper, lower)}"


def _bian_phrase(line: int, relation: str) -> str:
    if line % 2 == 1:
        return "末段主队加势, 可能扩大比分"
    return "末段客队加势, 存在偷球小概率"


def _wuxing_interact(a: str, b: str) -> str:
    ea, eb = _element_of(a), _element_of(b)
    if SHENG_CYCLE.get(ea) == eb:
        return "生"
    if KE_CYCLE.get(ea) == eb:
        return "克"
    if SHENG_CYCLE.get(eb) == ea:
        return "生"
    if KE_CYCLE.get(eb) == ea:
        return "克"
    return "比和"


def _wuxing_month_phrase(el: str) -> str:
    """简化: 不带月份, 描述五行本身状态。"""
    return f"{el} 旺于夏秋, 休于冬春, 主队根基{'稳固' if el in ('土', '金') else '中等'}"


def _render_score_hint(top3: list, relation: str, winner: str | None) -> str:
    """第 3 段: 卦数附会比分 (附会 + 必标"仅娱乐")。"""
    lines = []
    for i, s in enumerate(top3[:3], 1):
        label = {1: "最可能", 2: "次可能", 3: "小概率"}.get(i, f"#{i}")
        lines.append(f"{label}: {s['home']}:{s['away']} ({s['pct']:.0f}%)")
    winner_phrase = {
        "a": "主队胜",
        "b": "客队胜",
        None: "平局",
    }.get(winner, "")
    # 综合判定保持 winner 一致, 不二次添加附会 (卦象已在 hexagram_interpretation 表述)
    return " / ".join(lines) + f" / 附会: 仅娱乐, 综合判定 {winner_phrase}"


def _render_reality_check(team_a: str, team_b: str) -> str:
    """第 4 段: 客观赛事现实 (实力 + 战意 + 理性提醒)。"""
    return (
        f"实力对比: {team_a} 与 {team_b} 身价/阵容差距需结合 FIFA 排名与近 5 场战绩判断;\n"
        f"战意: 小组出线/淘汰赛阶段不同, 决定战术倾向;\n"
        f"提醒: 梅花易数仅传统文化游戏, 不能替代竞技分析, 切勿以此为投注依据, 理性观赛。"
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 4:
        sys.exit(f"Usage: {sys.argv[0]} <kickoff_utc> <team_a> <team_b>\n"
                 f"  e.g. {sys.argv[0]} '2026-06-24T19:00Z' 'Mexico' 'Switzerland'")
    import json
    result = qi_gua(sys.argv[1], sys.argv[2], sys.argv[3])
    print(json.dumps(result, ensure_ascii=False, indent=2))