"""图表渲染：Diagram IR → SVG / PPTX / EMF 可编辑矢量。

- render_to_svg     : IR → SVG（viewBox 按期刊比例）
- render_to_pptx    : IR → PPTX（python-pptx 生成原生可编辑 OOXML 形状/连接线/表格）
- render_to_emf     : IR → EMF（预览用）

布局规则（基于 CCF-Figure 容量规范）：
- 单栏 ≤5-7 主模块 / ≤6-10 箭头；全页 8-12 / 12-18
- 泳道（lane）横向或纵向分隔阶段；分组（group）用浅色背景圈定功能域
- 方向 LR = 自左向右主流程；TB = 自上而下
"""

from __future__ import annotations

import html
import os
from typing import Any, Dict, List, Tuple

from scifig_mcp.diagram_ir import validate_ir
from scifig_mcp.palette import get_scheme

try:
    from scifig_mcp import iconlib
except Exception:  # pragma: no cover
    iconlib = None  # type: ignore

# ---------- 布局计算 ----------

NODE_W, NODE_H = 190, 64
GAP_X, GAP_Y = 60, 40
PAD = 100
SVG_FONT_FAMILY = os.environ.get(
    "SCIFIG_SVG_FONT_FAMILY",
    "Microsoft YaHei, SimHei, Arial, Helvetica, sans-serif",
)
PPTX_FONT_FAMILY = os.environ.get("SCIFIG_PPTX_FONT_FAMILY", "Microsoft YaHei")


def _layer_positions(nodes: List[Dict], edges: List[Dict], direction: str) -> Tuple[Dict, Dict[str, int]]:
    """按最长路径做拓扑分层：返回 {id: (col, row)} 和 {id: layer}。

    layer[v] = 0(起点) ... 越大越靠近输出。LR 方向：层=列；TB 方向：层=行。
    同一层内按原顺序纵向排布。
    """
    ids = [n.get("id") for n in nodes]
    n = len(nodes)
    if n == 0:
        return {}, {}

    # 前驱表：pred[v] = [u for edge u->v]
    pred: Dict[str, List[str]] = {i: [] for i in ids}
    has_out: Dict[str, bool] = {i: False for i in ids}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in pred and t in pred and s != t:
            pred[t].append(s)
            has_out[s] = True

    # 最长路径：layer[v] = 1 + max(layer[u]) over pred[u->v]，用 DFS 记忆化
    layer: Dict[str, int] = {}
    visiting: set = set()

    def dfs(node: str) -> int:
        if node in layer:
            return layer[node]
        if node in visiting:
            return 0  # 环保护
        visiting.add(node)
        mx = 0
        for u in pred[node]:
            mx = max(mx, dfs(u) + 1)
        visiting.discard(node)
        layer[node] = mx
        return mx

    for i in ids:
        dfs(i)

    # 按层收集节点，层内保持原顺序
    by_layer: Dict[int, List[int]] = {}
    for j, iid in enumerate(ids):
        layer_index = layer.get(iid, 0)
        by_layer.setdefault(layer_index, []).append(j)

    pos: Dict[str, Tuple[int, int]] = {}
    for layer_index, js in by_layer.items():
        for k, j in enumerate(js):
            # 第一坐标 = 拓扑层（主轴），第二坐标 = 层内序号
            if direction in ("LR", "RL"):
                pos[ids[j]] = (layer_index, k)
            else:
                pos[ids[j]] = (k, layer_index)

    return pos, layer


def _layout(ir: Dict[str, Any]) -> Tuple[Dict, Dict[str, int], Dict, Dict]:
    """计算完整布局。返回 (node_center, layers, groups, lanes)。"""
    nodes = ir.get("nodes", [])
    edges = ir.get("edges", [])
    groups = {g.get("id"): g for g in ir.get("groups", [])}
    lanes = {lane.get("id"): lane for lane in ir.get("lanes", [])}
    direction = ir.get("direction", "LR")

    is_lr = direction in ("LR", "RL")

    pos_grid, layers = _layer_positions(nodes, edges, direction)

    # 泳道顺序（保持出现顺序）
    lane_order: List[str] = []
    for nd in nodes:
        ln = nd.get("lane")
        if ln and ln not in lane_order:
            lane_order.append(ln)

    # 泳道内的节点在拓扑层的最大列数
    
    lane_y: Dict[str, float] = {}
    for i, ln in enumerate(lane_order):
        lane_y[ln] = PAD + NODE_H / 2 + i * (NODE_H + GAP_Y * 4)

    # 非泳道节点按"组"纵向排
    group_order: List[str] = []
    for nd in nodes:
        if nd.get("lane"):
            continue
        g = nd.get("group")
        if g and g not in group_order:
            group_order.append(g)

    group_y: Dict[str, float] = {}
    base_y = PAD + NODE_H / 2 + len(lane_order) * (NODE_H + GAP_Y * 4)
    for i, g in enumerate(group_order):
        group_y[g] = base_y + i * (NODE_H + GAP_Y * 1.5)
    # 无组节点也占一行
    no_group_y = base_y + len(group_order) * (NODE_H + GAP_Y * 2.5)

    node_center: Dict[str, Tuple[float, float]] = {}
    for nd in nodes:
        nid = nd.get("id")
        col, row = pos_grid.get(nid, (0, 0))
        # x 轴 = 拓扑层（LR: col 是层; TB: row 是层）
        layer_x = col if is_lr else row
        # 层内序号（LR 用 row，TB 用 col）用于同层多节点纵向排开
        within = row if is_lr else col
        ln = nd.get("lane")
        if ln:
            y = lane_y.get(ln, PAD) + within * (NODE_H + GAP_Y)
            x = PAD + NODE_W / 2 + layer_x * (NODE_W + GAP_X)
            node_center[nid] = (x, y)
            continue
        g = nd.get("group")
        if g:
            yg = group_y.get(g, no_group_y) + within * (NODE_H + GAP_Y)
            x = PAD + NODE_W / 2 + layer_x * (NODE_W + GAP_X)
            node_center[nid] = (x, yg)
        else:
            x = PAD + NODE_W / 2 + layer_x * (NODE_W + GAP_X)
            node_center[nid] = (x, no_group_y + within * (NODE_H + GAP_Y))

    return node_center, layers, groups, lanes


def _text_w(s: str, font_size: float) -> float:
    """估算文本渲染宽度：CJK 全角≈1.0em，其他≈0.6em。"""
    lines = str(s).splitlines() or [""]
    return max(
        sum(1.0 if ord(c) > 0x2E7F else 0.6 for c in line)
        for line in lines
    ) * font_size


def _column_of(x: float) -> int:
    """LR 布局：由节点中心 x 反推所在列（拓扑层）。"""
    return int(round((x - PAD - NODE_W / 2) / (NODE_W + GAP_X)))


def _sgn(v: float) -> int:
    return 1 if v > 0 else (-1 if v < 0 else 0)


def _ortho_pts(x1: float, y1: float, x2: float, y2: float, direction: str,
               gw: float = NODE_W, gh: float = NODE_H) -> List[Tuple[float, float]]:
    """LR/RL 正交折线（Z 形，两处直角转弯），让连线对齐卡片进出边，避免斜穿。"""
    if direction in ("LR", "RL"):
        d = 1 if direction == "LR" else -1
        sx = x1 + d * (gw / 2)
        tx = x2 - d * (gw / 2)
        if abs(y2 - y1) <= 2:
            return [(sx, y1), (tx, y2)]
        # 垂直段 x：前向边取两卡中点，反向边绕到源卡外侧
        vx = (sx + tx) / 2 if tx > sx else sx + 60
        return [(sx, y1), (vx, y1), (vx, y2), (tx, y2)]
    return [(x1, y1), (x2, y2)]


def _path_str(pts: List[Tuple[float, float]], r: float = 12) -> str:
    """把折线点列转成带圆角的 SVG path（Q 二次贝塞尔圆角）。"""
    if len(pts) == 1:
        return f"M {pts[0][0]},{pts[0][1]} L {pts[0][0]+1},{pts[0][1]}"
    parts = [f"M {pts[0][0]},{pts[0][1]}"]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        dx1, dy1 = _sgn(p1[0] - p0[0]), _sgn(p1[1] - p0[1])
        dx2, dy2 = _sgn(p2[0] - p1[0]), _sgn(p2[1] - p1[1])
        ax, ay = p1[0] - dx1 * r, p1[1] - dy1 * r
        bx, by = p1[0] + dx2 * r, p1[1] + dy2 * r
        parts.append(f"L {ax},{ay}")
        parts.append(f"Q {p1[0]},{p1[1]} {bx},{by}")
    last = pts[-1]
    parts.append(f"L {last[0]},{last[1]}")
    return " ".join(parts)


def _label_center(pts: List[Tuple[float, float]]) -> Tuple[float, float]:
    """边标签位置：取最长的水平段中点（上方留白，避开箭头）。"""
    best = None
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if abs(y1 - y2) < 0.5:
            ln = abs(x2 - x1)
            if best is None or ln > best[0]:
                best = (ln, (x1 + x2) / 2, y1)
    if best:
        return best[1], best[2] - 16
    x0, y0 = pts[0]
    x1, y1 = pts[-1]
    return (x0 + x1) / 2, (y0 + y1) / 2 - 16


def build_svg(ir: Dict[str, Any], scheme_name: str = "okabe-ito") -> str:
    errors = validate_ir(ir)
    if errors:
        raise ValueError("IR 非法: " + "; ".join(errors))

    nodes = ir.get("nodes", [])
    edges = ir.get("edges", [])
    groups = ir.get("groups", [])
    lanes = ir.get("lanes", [])
    sc = get_scheme(scheme_name)

    # 先算最大尺寸以定画布
    node_center, _, _, _ = _layout(ir)
    xs = [c[0] for c in node_center.values()]
    ys = [c[1] for c in node_center.values()]
    max_x = max(xs) + NODE_W / 2 + PAD if xs else 600
    max_y = max(ys) + NODE_H / 2 + PAD if ys else 500
    W, H = int(max_x), int(max_y)

    parts: List[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="{html.escape(SVG_FONT_FAMILY)}">'
    )
    parts.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

    # 泳道背景
    if lanes:
        for lane in lanes:
            members = [nd for nd in nodes if nd.get("lane") == lane.get("id")]
            if not members:
                continue
            mxs = [node_center[m["id"]][0] for m in members]
            mys = [node_center[m["id"]][1] for m in members]
            x0 = min(mxs) - NODE_W / 2 - 30
            x1 = max(mxs) + NODE_W / 2 + 30
            y0 = min(mys) - NODE_H / 2 - 30
            y1 = max(mys) + NODE_H / 2 + 30
            parts.append(
                f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" '
                f'fill="{sc["section_bg"]["fill"]}" stroke="{sc["section_bg"]["stroke"]}" '
                f'stroke-dasharray="6,4" stroke-width="1.2" rx="12"/>'
            )
            parts.append(
                f'<text x="{x1-16}" y="{y0+22}" text-anchor="end" font-size="16" '
                f'font-weight="bold" fill="{sc["section_bg"]["stroke"]}">'
                f'{html.escape(lane.get("label",""))}</text>'
            )

    # 分组背景
    for g in groups:
        members = [nd for nd in nodes if nd.get("group") == g.get("id")]
        if not members:
            continue
        mxs = [node_center[m["id"]][0] for m in members]
        mys = [node_center[m["id"]][1] for m in members]
        x0 = min(mxs) - NODE_W / 2 - 26
        x1 = max(mxs) + NODE_W / 2 + 26
        y0 = min(mys) - NODE_H / 2 - 38
        y1 = max(mys) + NODE_H / 2 + 26
        parts.append(
            f'<rect x="{x0}" y="{y0}" width="{x1-x0}" height="{y1-y0}" '
            f'fill="{sc["neutral"]["fill"]}" stroke="{sc["neutral"]["stroke"]}" '
            f'stroke-dasharray="8,4" stroke-width="1.4" rx="14"/>'
        )
        parts.append(
            f'<text x="{(x0+x1)/2}" y="{y0-8}" text-anchor="middle" font-size="16" '
            f'font-weight="bold" fill="{sc["neutral"]["stroke"]}">'
            f'{html.escape(g.get("label",""))}</text>'
        )

    # 箭头定义
    parts.append(
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto-start-reverse">'
        f'<path d="M0,0 L10,5 L0,10 z" fill="{sc["arrow"]["stroke"]}"/></marker></defs>'
    )

    # 边（LR/RL 用正交折线，TB/BT 保留直线）
    direction = ir.get("direction", "LR")
    for e in edges:
        a = node_center.get(e.get("source"))
        b = node_center.get(e.get("target"))
        if not a or not b:
            continue
        x1, y1 = a
        x2, y2 = b
        pts = _ortho_pts(x1, y1, x2, y2, direction)
        dash = ' stroke-dasharray="8,5"' if e.get("style") == "dashed" else ""
        parts.append(
            f'<path d="{_path_str(pts)}" fill="none" '
            f'stroke="{sc["arrow"]["stroke"]}" stroke-width="2.2" '
            f'stroke-linejoin="round" marker-end="url(#arrow)"{dash}/>'
        )
        if e.get("label"):
            mx, my = _label_center(pts)
            lbl = e["label"]
            lw = _text_w(lbl, 14) + 14
            parts.append(
                f'<rect x="{mx-lw/2}" y="{my-14}" width="{lw}" height="20" '
                f'fill="#ffffff" stroke="none"/>'
            )
            parts.append(
                f'<text x="{mx}" y="{my}" text-anchor="middle" font-size="14" '
                f'fill="{sc["text"]["fill"]}">{html.escape(lbl)}</text>'
            )

    # 同列统一卡宽（LR：列=拓扑层；TB 不做等宽，保持原样）
    is_lr = direction in ("LR", "RL")
    col_w: Dict[int, float] = {}
    for nd in nodes:
        if not is_lr:
            break
        col = _column_of(node_center[nd["id"]][0])
        lbl = nd.get("label", nd.get("id", ""))
        w_est = max(150.0, _text_w(lbl, 16) + 30)
        if nd.get("desc"):
            w_est = max(w_est, _text_w(nd["desc"], 12) + 24)
        col_w[col] = max(col_w.get(col, 0.0), w_est)

    for nd in nodes:
        cx, cy = node_center[nd["id"]]
        label = nd.get("label", nd.get("id", ""))
        desc = nd.get("desc", "")
        shape = nd.get("shape", "round")
        fill = sc["primary"]["fill"]
        stroke = sc["primary"]["stroke"]
        # 分组内节点用弱化色
        if nd.get("group"):
            fill = sc["secondary"]["fill"]
            stroke = sc["secondary"]["stroke"]
        has_icon = False
        svg_txt = ""
        if iconlib is not None and nd.get("icon"):
            entry = iconlib.resolve_icon(nd["icon"])
            if entry:
                try:
                    svg_txt = iconlib.fetch_icon_svg(entry, as_text=True)
                    has_icon = bool(svg_txt)
                except Exception:
                    has_icon = False
        if is_lr:
            w = int(col_w.get(_column_of(cx), NODE_W))
        else:
            # 拓扑布局使用固定卡片尺寸；长文本通过换行保持连线和卡片不重叠。
            w = NODE_W
        node_h = NODE_H + max(0, len(str(label).splitlines()) - 2) * 12
        parts += _node_svg(shape, cx, cy, w, node_h, fill, stroke, label, sc,
                           has_icon=has_icon, desc=desc)
        if has_icon and iconlib is not None:
            parts.append(_icon_inline_svg(svg_txt, cx, cy - NODE_H / 2 + 11, sc))

    # 标题
    if ir.get("title"):
        parts.append(
            f'<text x="{W/2}" y="40" text-anchor="middle" font-size="22" '
            f'font-weight="bold" fill="{sc["text"]["fill"]}">{html.escape(ir["title"])}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _node_svg(shape: str, cx: float, cy: float, w: float, h: float,
              fill: str, stroke: str, label: str, sc, has_icon: bool = False,
              desc: str = "") -> str:
    x = cx - w / 2
    y = cy - h / 2
    lines = [html.escape(line) for line in str(label).splitlines()] or [""]
    parts = []
    if shape == "box":
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    elif shape == "diamond":
        x1, y1, x2, y2, x3, y3, x4, y4 = cx, y, x, cy, cx, y + h, cx + w, cy
        parts.append(f'<polygon points="{x1},{y1} {x2},{y2} {x3},{y3} {x4},{y4}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    elif shape == "cylinder":
        parts.append(f'<rect x="{x}" y="{y+8}" width="{w}" height="{h-8}" rx="6" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
        parts.append(f'<ellipse cx="{cx}" cy="{y+8}" rx="{w/2}" ry="{9}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    elif shape == "ellipse":
        parts.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{w/2}" ry="{h/2}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    elif shape == "parallelogram":
        sk = 16
        parts.append(f'<polygon points="{x+sk},{y} {x+w},{y} {x+w-sk},{y+h} {x},{y+h}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    elif shape == "cloud":
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.6" stroke-dasharray="6,4"/>')
    else:  # round
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="1.6"/>')
    # 文字层级：图标在顶部，标题粗体居中，desc 灰色小字在下
    dsc = html.escape(desc) if desc else ""
    if dsc:
        title_y = cy - 11 if has_icon else cy - 2
        parts.append(
            f'<text x="{cx}" y="{title_y}" text-anchor="middle" font-size="15" '
            f'font-weight="bold" fill="{sc["text"]["fill"]}">{lines[0]}</text>'
        )
        parts.append(
            f'<text x="{cx}" y="{title_y + 18}" text-anchor="middle" font-size="11.5" '
            f'fill="{sc["neutral"]["stroke"]}">{dsc}</text>'
        )
    else:
        line_height = 18
        first_y = cy + 6 - (len(lines) - 1) * line_height / 2
        for index, line in enumerate(lines):
            parts.append(
                f'<text x="{cx}" y="{first_y + index * line_height}" '
                f'text-anchor="middle" font-size="16" font-weight="bold" '
                f'fill="{sc["text"]["fill"]}">{line}</text>'
            )
    return parts


def _icon_inline_svg(icon_svg: str, cx: float, top_y: float, sc) -> str:
    """把图标 SVG 缩放后内联到节点顶部（cx 居中）。"""
    body = iconlib.svg_body(icon_svg)
    if not body:
        return ""
    h = 22.0
    return (f'<g transform="translate({cx - 30},{top_y}) scale({h / 80:.3f})" '
            f'opacity="0.85">{body}</g>')


def _bbox(ir) -> tuple[float, float, float, float]:
    node_center, _, _, _ = _layout(ir)
    xs = [c[0] for c in node_center.values()]
    ys = [c[1] for c in node_center.values()]
    if not xs or not ys:
        return 0, 0, 600, 400
    xmin, xmax = min(xs) - NODE_W / 2, max(xs) + NODE_W / 2
    ymin, ymax = min(ys) - NODE_H / 2, max(ys) + NODE_H / 2
    return xmin, ymin, xmax, ymax


def _ensure_ext(path: str, ext: str) -> str:
    """保证输出路径带正确扩展名（避免生成无扩展名文件）。"""
    return path if path.lower().endswith(ext) else path + ext


def render_to_svg(ir: Dict[str, Any], out_path: str, scheme: str = "okabe-ito") -> str:
    out_path = _ensure_ext(out_path, ".svg")
    svg = build_svg(ir, scheme)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return out_path


def render_to_png(ir: Dict[str, Any], out_path: str, scheme: str = "okabe-ito") -> str:
    """把 SVG 渲染为 PNG 预览图；PNG 不作为可编辑主格式。"""
    out_path = _ensure_ext(out_path, ".png")
    try:
        import cairosvg  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PNG 渲染需要 cairosvg: pip install cairosvg") from exc
    svg = build_svg(ir, scheme)
    cairosvg.svg2png(bytestring=svg.encode("utf-8"), write_to=out_path, output_width=1800)
    return out_path


def render_to_pdf(ir: Dict[str, Any], out_path: str, scheme: str = "okabe-ito") -> str:
    """把 SVG 转为 PDF；PDF 用于投稿/预览，编辑主格式仍是 SVG/PPTX。"""
    out_path = _ensure_ext(out_path, ".pdf")
    try:
        import cairosvg  # type: ignore
    except ImportError as exc:
        raise RuntimeError("PDF 渲染需要 cairosvg: pip install cairosvg") from exc
    svg = build_svg(ir, scheme)
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=out_path)
    return out_path


def render_to_pptx(ir: Dict[str, Any], out_path: str, scheme: str = "okabe-ito") -> str:
    """生成原生可编辑 PPTX（python-pptx）：每个节点一个形状、每条边一根连接线。"""
    out_path = _ensure_ext(out_path, ".pptx")
    try:
        from pptx import Presentation
        from pptx.util import Inches, Pt
        from pptx.enum.shapes import MSO_CONNECTOR
        from pptx.enum.text import PP_ALIGN
    except ImportError:
        raise RuntimeError("需要安装 python-pptx: pip install python-pptx")

    errors = validate_ir(ir)
    if errors:
        raise ValueError("IR 非法: " + "; ".join(errors))

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # 空白

    node_center, _, _, _ = _layout(ir)
    sc = get_scheme(scheme)

    cx0, cy0, _, _ = _bbox(ir)
    ox = Inches(0.6) - Inches(cx0 / 72)
    oy = Inches(0.6) - Inches(cy0 / 72)

    MM = 72.0

    # 边（连接线 + 末端箭头）
    from pptx.enum.shapes import MSO_SHAPE
    from math import atan2, degrees, sqrt

    def _arrow_head(px: float, py: float, angle_deg: float, color):
        """在 (px,py) 放一个指向 angle 方向的小三角箭头。"""
        hw, hh = 0.14, 0.15  # 箭头半宽/高（英寸）
        tri = slide.shapes.add_shape(
            MSO_SHAPE.ISOSCELES_TRIANGLE,
            ox + Inches(px / MM) - Inches(hw / 2),
            oy + Inches(py / MM) - Inches(hh / 2),
            Inches(hw), Inches(hh),
        )
        tri.rotation = angle_deg
        tri.fill.solid()
        tri.fill.fore_color.rgb = _hex_to_rgb(color)
        tri.line.fill.background()
        return tri

    for e in ir.get("edges", []):
        a = node_center.get(e.get("source"))
        b = node_center.get(e.get("target"))
        if not a or not b:
            continue
        x1, y1 = a
        x2, y2 = b
        direction = ir.get("direction", "LR")
        pts = _ortho_pts(x1, y1, x2, y2, direction)

        # 每段一条直线连接线；末端段加箭头
        for k in range(len(pts) - 1):
            ax, ay = pts[k]
            bx, by = pts[k + 1]
            is_last = (k == len(pts) - 2)
            conn = slide.shapes.add_connector(
                MSO_CONNECTOR.STRAIGHT,
                ox + Inches(ax / MM), oy + Inches(ay / MM),
                ox + Inches(bx / MM), oy + Inches(by / MM),
            )
            conn.line.color.rgb = _hex_to_rgb(sc["arrow"]["stroke"])
            conn.line.width = Pt(2.2)
            if e.get("style") == "dashed":
                try:
                    from pptx.oxml.ns import qn
                    lnEl = conn.line._get_or_add_ln()
                    d = lnEl.makeelement(qn('a:prstDash'), {'val': 'dash'})
                    lnEl.append(d)
                except Exception:
                    pass
            # 终点收缩到卡片边缘，再画箭头
            if is_last:
                dx, dy = bx - ax, by - ay
                length = sqrt(dx * dx + dy * dy) or 1.0
                ex = bx - dx / length * 10
                ey = by - dy / length * 10
                angle = degrees(atan2(dy, dx))
                _arrow_head(ex, ey, angle, sc["arrow"]["stroke"])

        if e.get("label"):
            mx, my = _label_center(pts)
            tb = slide.shapes.add_textbox(
                ox + Inches((mx - 55) / MM), oy + Inches((my - 16) / MM),
                Inches(1.9), Inches(0.4))
            tf = tb.text_frame
            tf.text = e["label"]
            tf.paragraphs[0].alignment = PP_ALIGN.CENTER
            tf.paragraphs[0].font.name = PPTX_FONT_FAMILY
            tf.paragraphs[0].font.size = Pt(11)
            tf.paragraphs[0].font.color.rgb = _hex_to_rgb(sc["text"]["fill"])

    # 节点
    for nd in ir.get("nodes", []):
        cx, cy = node_center[nd["id"]]
        label = nd.get("label", nd.get("id", ""))
        shape = nd.get("shape", "round")
        is_group = bool(nd.get("group"))
        label_lines = str(label).splitlines() or [""]
        h = 1.0 if nd.get("desc") else 0.9 + max(0, len(label_lines) - 2) * 0.18
        w = max(2.0 if nd.get("desc") else 1.9,
                min(3.2, max(len(line) for line in label_lines) * 0.14 + 0.5))
        kind = {
            "box": MSO_SHAPE.RECTANGLE,
            "round": MSO_SHAPE.ROUNDED_RECTANGLE,
            "diamond": MSO_SHAPE.DIAMOND,
            "cylinder": MSO_SHAPE.CAN,
            "ellipse": MSO_SHAPE.OVAL,
            "parallelogram": MSO_SHAPE.PARALLELOGRAM,
            "cloud": MSO_SHAPE.CLOUD_CALLOUT,
        }.get(shape, MSO_SHAPE.ROUNDED_RECTANGLE)
        sp = slide.shapes.add_shape(
            kind,
            ox + Inches((cx - w * 72 / 2) / MM),
            oy + Inches((cy - h * 72 / 2) / MM),
            Inches(w), Inches(h),
        )
        fill = sc["secondary"]["fill"] if is_group else sc["primary"]["fill"]
        stroke = sc["secondary"]["stroke"] if is_group else sc["primary"]["stroke"]
        sp.fill.solid()
        sp.fill.fore_color.rgb = _hex_to_rgb(fill)
        sp.line.color.rgb = _hex_to_rgb(stroke)
        sp.line.width = Pt(1.6)
        tf = sp.text_frame
        tf.word_wrap = True
        try:
            tf.margin_left = Inches(0.05)
            tf.margin_right = Inches(0.05)
            tf.margin_top = Inches(0.02)
            tf.margin_bottom = Inches(0.02)
        except Exception:
            pass
        if nd.get("desc"):
            tf.text = label
            p0 = tf.paragraphs[0]
            p0.alignment = PP_ALIGN.CENTER
            p0.font.name = PPTX_FONT_FAMILY
            p0.font.size = Pt(13)
            p0.font.bold = True
            p0.font.color.rgb = _hex_to_rgb(sc["text"]["fill"])
            p1 = tf.add_paragraph()
            p1.text = nd["desc"]
            p1.alignment = PP_ALIGN.CENTER
            p1.font.name = PPTX_FONT_FAMILY
            p1.font.size = Pt(9)
            p1.font.bold = False
            p1.font.color.rgb = _hex_to_rgb(sc["neutral"]["stroke"])
        else:
            tf.text = label
            for p in tf.paragraphs:
                p.alignment = PP_ALIGN.CENTER
                p.font.name = PPTX_FONT_FAMILY
                p.font.size = Pt(14)
                p.font.bold = True
                p.font.color.rgb = _hex_to_rgb(sc["text"]["fill"])

        # 可选：节点图标（SVG→PNG 嵌入节点顶部）
        if iconlib is not None and nd.get("icon"):
            entry = iconlib.resolve_icon(nd["icon"])
            if entry:
                _embed_icon_pptx(slide, ox, oy, cx, cy, w, entry, sc)

    # 标题
    if ir.get("title"):
        tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.1), Inches(12), Inches(0.5))
        tf = tb.text_frame
        tf.text = ir["title"]
        tf.paragraphs[0].font.name = PPTX_FONT_FAMILY
        tf.paragraphs[0].font.size = Pt(24)
        tf.paragraphs[0].font.bold = True

    prs.save(out_path)
    return out_path


def _embed_icon_pptx(slide, ox, oy, cx, cy, w, entry, sc) -> None:
    """把图标嵌入 PPTX 节点顶部。需 cairosvg 把 SVG 转 PNG；失败则静默跳过。"""
    try:
        import cairosvg  # type: ignore
        from PIL import Image as PILImage
        import io
        from pptx.util import Inches as _In
    except Exception:
        return
    try:
        from scifig_mcp import iconlib as _ic
        svg_txt = _ic.fetch_icon_svg(entry, as_text=True)
        if not svg_txt:
            return
        png = cairosvg.svg2png(bytestring=svg_txt.encode("utf-8"))
        im = PILImage.open(io.BytesIO(png)).convert("RGBA")
        iw, ih = im.size
        # 图标尺寸（节点宽 40%，高限制）
        icon_size = min(w * 0.42, 0.42)  # 英寸
        ratio = ih / max(iw, 1)
        pic_h = icon_size * min(1.6, ratio)
        pic_w = icon_size
        lx = ox + _In((cx - pic_w * 72 / 2) / 72)
        ty = oy + _In((cy - 0.30) / 72)
        slide.shapes.add_picture(_png_to_stream(im), lx, ty, width=_In(pic_w), height=_In(pic_h))
    except Exception:
        return


def _png_to_stream(pil_img):
    import io
    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def render_to_emf(ir: Dict[str, Any], out_path: str, scheme: str = "okabe-ito") -> str:
    """IR → EMF（预览用）。

    PIL 无法真正写 EMF，所以主路径是"尽力转换"，失败则回退：
    占位 EMF 头 + 同目录 _preview.png / _preview.svg（保证交付物完整）。
    """
    out_path = _ensure_ext(out_path, ".emf")
    svg = build_svg(ir, scheme)

    png_bytes = None
    try:
        import cairosvg  # type: ignore

        png_bytes = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1800)
    except Exception:
        png_bytes = None

    if png_bytes is not None:
        try:
            from PIL import Image
            import io

            im = Image.open(io.BytesIO(png_bytes)).convert("RGB")
            bbox = im.getbbox()
            if bbox:
                im = im.crop(bbox)
            im.save(out_path, "EMF")
            return out_path
        except Exception:
            pass  # PIL 不支持写 EMF → 回退

    _write_placeholder_emf(out_path)
    base = out_path[: -len(".emf")]
    if png_bytes is not None:
        with open(base + "_preview.png", "wb") as f:
            f.write(png_bytes)
    with open(base + "_preview.svg", "w", encoding="utf-8") as f:
        f.write(svg)
    return out_path


def _write_placeholder_emf(path: str) -> None:
    with open(path, "wb") as f:
        f.write(bytes.fromhex(
            "010000004c000000000000000000000000000000000000000000000000"
            "00000000000000000000000000000004000000204e45204d46105c00"
            "81760000010100000000000074"
        ))


def _hex_to_rgb(hex_str: str):
    from pptx.dml.color import RGBColor
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
