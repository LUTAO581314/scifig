"""8-role 语义配色 + 多套预设（借鉴 academic-figure-generator 思路）。

prompt/IR 用 role 名（primary/secondary/...）而非 hex，渲染时按主题替换，
这样既能整体换主题，又保证语义一致。默认 Okabe-Ito 色盲友好。
"""

from __future__ import annotations

from typing import Dict, List

# 每个 role: {fill, stroke, text}
Scheme = Dict[str, Dict[str, str]]


def _scheme(primary, secondary, accent, neutral_bg, border, text,
            p_stroke=None, s_stroke=None, a_stroke=None) -> Scheme:
    return {
        "primary":   {"fill": primary,   "stroke": p_stroke or border, "text": text},
        "secondary": {"fill": secondary, "stroke": s_stroke or border, "text": text},
        "accent":    {"fill": accent,    "stroke": a_stroke or border, "text": text},
        "neutral":   {"fill": neutral_bg, "stroke": border, "text": text},
        "section_bg": {"fill": neutral_bg, "stroke": border, "text": text},
        "text":      {"fill": text,       "stroke": "none",   "text": text},
        "border":    {"fill": "none",     "stroke": border,    "text": text},
        "arrow":     {"fill": text,       "stroke": text,      "text": text},
    }


# Okabe-Ito 色盲友好（默认，期刊标配）
OKABE_ITO = _scheme(
    primary="#0072B2", secondary="#56B4E9",
    accent="#D55E00", neutral_bg="#F0F0F0",
    border="#333333", text="#111111",
)

# Nature/Science 低饱和期刊风
NATURE = _scheme(
    primary="#4E79A7", secondary="#9ECAE1",
    accent="#E15759", neutral_bg="#F7F7F7",
    border="#666666", text="#1a1a1a",
)

# IEEE 工程风
IEEE = _scheme(
    primary="#0072BD", secondary="#7CAFC4",
    accent="#A2142F", neutral_bg="#F2F2F2",
    border="#404040", text="#000000",
)

# 明亮撞色（教学/汇报用）
VIVID = _scheme(
    primary="#E6194B", secondary="#3CB44B",
    accent="#FFE119", neutral_bg="#FAFAFA",
    border="#333333", text="#111111",
)

# 柔和粉彩（现代 ML 会议风）
PASTEL = _scheme(
    primary="#7CB5EC", secondary="#A6D99C",
    accent="#F7A8B8", neutral_bg="#FBFBFB",
    border="#8A8A8A", text="#2E2E2E",
)

# 论文高级感"浅色扁平"（低饱和填充 + 同色系深描边 + 圆角卡片）
PAPER_SOFT = _scheme(
    primary="#E8F1F8", secondary="#E6F4EA", accent="#FDF0E7",
    neutral_bg="#F7F9FB", border="#8FA3B0", text="#333C44",
    p_stroke="#4A7BA6", s_stroke="#4A8B5F", a_stroke="#C97B4A",
)

SCHEMES: Dict[str, Scheme] = {
    "okabe-ito": OKABE_ITO,
    "nature": NATURE,
    "ieee": IEEE,
    "vivid": VIVID,
    "pastel": PASTEL,
    "paper-soft": PAPER_SOFT,
}


def get_scheme(name: str = "okabe-ito") -> Scheme:
    return SCHEMES.get(name, OKABE_ITO)


def color_names() -> List[str]:
    return list(SCHEMES.keys())
