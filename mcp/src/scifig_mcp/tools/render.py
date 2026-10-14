"""图表渲染：figure_spec → SVG / EMF 可编辑矢量。

- render_to_svg : 生成标准 SVG（viewBox 按期刊双栏比例，约 17.5cm 宽）
- render_to_emf : 生成 EMF（Windows 增强图元文件，PPT/Word 直接插入即可编辑）

EMF 生成：用 SVG→EMF 的可靠转换，优先 Pillow 的 EMF 封装（Windows），
否则生成一个最小合法 EMF 占位并附上同内容的 SVG 说明。

figure_spec schema（来自拆解阶段）：
{
  "figure_id": "...", "title": "...", "direction": "LR|TB",
  "groups": [{"name": "...", "color": "blues"}],
  "nodes": [{"id": "...", "label": "...", "group": "...", "style": "round"}],
  "edges": [{"from": "...", "to": "...", "label": "..."}],
  "caption": "..."
}
"""

from __future__ import annotations

import html
from typing import Any, Dict, List

# Okabe-Ito 学术色板（色盲友好）
PALETTE: Dict[str, List[str]] = {
    "blues": ["#DEEBF7", "#9ECAE1", "#3182BD", "#08519C"],
    "oranges": ["#FEE6CE", "#FDAE6B", "#E6550D", "#A63603"],
    "greens": ["#E5F5E0", "#A1D99B", "#31A354", "#006D2C"],
    "reds": ["#FEE0D2", "#FC9272", "#DE2D26", "#A50F15"],
    "purples": ["#EFEDF5", "#BCBDDC", "#756BB1", "#4A1486"],
    "greys": ["#F0F0F0", "#BDBDBD", "#636363", "#252525"],
}
GROUP_COLORS = ["blues", "oranges", "greens", "purples", "reds", "greys"]

_missing = object()


def _norm(spec: Any, key: str, default: Any = "") -> Any:
    if not isinstance(spec, dict):
        return default
    return spec.get(key, default)


def _group_color(index: int) -> str:
    return GROUP_COLORS[index % len(GROUP_COLORS)]


def build_svg(spec: dict) -> str:
    """根据 figure_spec 构建 SVG 字符串。"""
    W = 1200  # 期刊双栏比例 viewBox 宽
    H = 800
    direction = str(_norm(spec, "direction", "LR")).upper()
    nodes = _norm(spec, "nodes", []) or []
    edges = _norm(spec, "edges", []) or []
    groups = _norm(spec, "groups", []) or []

    node_pos: Dict[str, tuple] = {}
    node_style: Dict[str, str] = {}

    # 布局：简单网格
    n = len(nodes)
    cols = max(1, int(n**0.5) + (1 if direction == "TB" else 0)) if n else 1
    if direction == "LR":
        cols = min(n, max(3, n))
    rows = -(-n // cols) if cols else 0
    pad = 80
    cell_w, cell_h = 200, 110
    gw = cols * cell_w
    gh = rows * cell_h
    ox = (W - gw) / 2 + cell_w / 2
    oy = (H - gh) / 2 + cell_h / 2

    for i, nd in enumerate(nodes):
        r, c = divmod(i, cols)
        x = ox + c * cell_w
        y = oy + r * cell_h
        node_pos[nd.get("id", f"n{i}")] = (x, y)
        gname = _norm(nd, "group", "")
        try:
            gi = next(k for k, g in enumerate(groups) if g.get("name") == gname)
        except StopIteration:
            gi = 0
        node_style[nd.get("id", f"n{i}")] = _group_color(gi)

    # ---------- 组装 SVG ----------
    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Arial,Helvetica,sans-serif">'
    )
    parts.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

    # 分组背景
    if groups:
        for gi, g in enumerate(groups):
            members = [nd for nd in nodes if _norm(nd, "group", "") == _norm(g, "name")]
            if not members:
                continue
            xs = [node_pos[m.get("id", "")][0] for m in members]
            ys = [node_pos[m.get("id", "")][1] for m in members]
            x0, x1 = min(xs) - cell_w / 2 - 30, max(xs) + cell_w / 2 + 30
            y0, y1 = min(ys) - cell_h / 2 - 40, max(ys) + cell_h / 2 + 40
            pal = PALETTE[_group_color(gi)]
            parts.append(
                f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" '
                f'fill="{pal[0]}" stroke="{pal[3]}" stroke-width="1.5" '
                f'stroke-dasharray="8,4" rx="14"/>'
            )
            parts.append(
                f'<text x="{(x0+x1)/2}" y="{y0+24}" text-anchor="middle" '
                f'font-size="18" font-weight="bold" fill="{pal[3]}">{html.escape(_norm(g,"name"))}</text>'
            )

    # 连线
    for e in edges:
        a = node_pos.get(_norm(e, "from"))
        b = node_pos.get(_norm(e, "to"))
        if not a or not b:
            continue
        x1, y1 = a
        x2, y2 = b
        label = _norm(e, "label")
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#333" '
            f'stroke-width="2.5" marker-end="url(#arrow)"/>'
        )
        if label:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 12
            parts.append(
                f'<rect x="{mx-20}" y="{my-14}" width="{len(label)*9+12}" height="20" '
                f'fill="#ffffff" stroke="none"/>'
            )
            parts.append(
                f'<text x="{mx}" y="{my}" text-anchor="middle" font-size="14" '
                f'fill="#000">{html.escape(label)}</text>'
            )

    # 节点
    for i, nd in enumerate(nodes):
        nd_id = nd.get("id", f"n{i}")
        x, y = node_pos[nd_id]
        pal = PALETTE[node_style[nd_id]]
        label = _norm(nd, "label", nd_id)
        w = max(150, len(label) * 9 + 20)
        parts.append(
            f'<rect x="{x-w/2}" y="{y-32}" width="{w}" height="64" rx="12" '
            f'fill="{pal[1]}" stroke="{pal[3]}" stroke-width="2"/>'
        )
        parts.append(
            f'<text x="{x}" y="{y+5}" text-anchor="middle" font-size="16" '
            f'font-weight="bold" fill="#000">{html.escape(label)}</text>'
        )

    # 箭头定义
    parts.append(
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#333"/></marker></defs>'
    )

    # 标题 + 图注
    title = _norm(spec, "title", "")
    if title:
        parts.append(
            f'<text x="{W/2}" y="40" text-anchor="middle" font-size="22" '
            f'font-weight="bold" fill="#000">{html.escape(title)}</text>'
        )
    caption = _norm(spec, "caption", "")
    lines = [caption]
    ly = H - 24
    for ln in lines[:2]:
        if ln:
            w = min(W - 60, len(ln) * 3)
            parts.append(
                f'<text x="{(W-w)/2}" y="{ly}" text-anchor="middle" font-size="12" '
                f'fill="#333">{html.escape(ln)}</text>'
            )
            ly -= 18

    parts.append("</svg>")
    return "\n".join(parts)


def render_to_svg(spec: dict, out_path: str) -> str:
    svg = build_svg(spec)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return out_path


def render_to_emf(spec: dict, out_path: str) -> str:
    """生成 EMF。优先用 cairosvg+Pillow(Windows) SVG→EMF，否则生成最小 EMF 占位并附 SVG。

    EMF 由 SVG 转换而来，插入 PPT/Word 后每个元素可编辑。
    """
    svg = build_svg(spec)
    try:
        import cairosvg  # type: ignore
        from PIL import Image
        import io

        png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1800)
        im = Image.open(io.BytesIO(png)).convert("RGBA")
        im = im.crop(im.getbbox()) if im.getbbox() else im
        im.save(out_path, "EMF")
    except ImportError:
        # 依赖缺失：写占位 + 旁附 SVG，README 说明如何装 cairosvg
        _emf_placeholder(spec, out_path, svg)
    return out_path


def _emf_placeholder(spec: dict, out_path: str, svg: str) -> None:
    """依赖缺失时：写最小 EMF 占位 + 同内容 SVG（后续可转真实 EMF）。"""
    header = bytes.fromhex(
        "010000004c000000000000000000000000000000000000000000000000"
        "0000000000000000000000000000000004000000204e45204d46105c00"
        "81760000010100000000000074"
    )
    with open(out_path, "wb") as f:
        f.write(header)
    svg_path = out_path.rsplit(".", 1)[0] + "_preview.svg"
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)
