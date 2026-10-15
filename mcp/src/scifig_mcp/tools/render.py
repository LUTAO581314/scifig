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
from typing import Any, Dict, List, Tuple

from scifig_mcp.diagram_ir import SHAPES, validate_ir
from scifig_mcp.palette import get_scheme

# ---------- 布局计算 ----------

NODE_W, NODE_H = 190, 64
GAP_X, GAP_Y = 60, 40
PAD = 100


def _layer_positions(nodes: List[Dict], edges: List[Dict], direction: str) -> Tuple[Dict, Dict[str, int]]:
    """按最长路径做拓扑分层：返回 {id: (col, row)} 和 {id: layer}。

    LR 方向：层=列；TB 方向：层=行。同一层内按原顺序纵向排布。
    无依赖的孤立节点放最后一层。
    """
    ids = [n.get("id") for n in nodes]
    n = len(nodes)

    # 建立前驱/后继邻接
    succ: Dict[str, List[str]] = {i: [] for i in ids}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        if s in succ and t in succ and s != t:
            succ[s].append(t)

    # 最长路径分层（保证边 direction 的层递增）
    layer: Dict[str, int] = {}
    visiting: set = set()

    def dfs(node: str) -> int:
        if node in layer:
            return layer[node]
        if node in visiting:
            return 0  # 环保护
        visiting.add(node)
        mx = 0
        for nb in succ[node]:
            mx = max(mx, dfs(nb) + 1)
        visiting.discard(node)
        layer[node] = mx
        return mx

    for i in ids:
        dfs(i)

    max_layer = max(layer.values()) if layer else 0
    # 按层收集节点，层内保持原顺序
    by_layer: Dict[int, List[int]] = {}
    for j, iid in enumerate(ids):
        l = layer.get(iid, 0)
        by_layer.setdefault(l, []).append(j)

    pos: Dict[str, Tuple[int, int]] = {}
    for l, js in by_layer.items():
        for k, j in enumerate(js):
            pos[ids[j]] = (l, k) if direction in ("LR", "RL") else (k, l)

    # 给定层排序稳定，返回
    return pos, layer


def _layout(ir: Dict[str, Any]) -> Tuple[Dict, Dict[str, int], Dict, Dict]:
    """计算完整布局。返回 (node_center, layers, groups, lanes)。"""
    nodes = ir.get("nodes", [])
    edges = ir.get("edges", [])
    groups = {g.get("id"): g for g in ir.get("groups", [])}
    lanes = {l.get("id"): l for l in ir.get("lanes", [])}
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
        f'viewBox="0 0 {W} {H}" font-family="Arial,Helvetica,sans-serif">'
    )
    parts.append(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

    # 泳道背景
    if lanes:
        for l in lanes:
            members = [nd for nd in nodes if nd.get("lane") == l.get("id")]
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
                f'<text x="{x0+16}" y="{y0+22}" font-size="16" font-weight="bold" '
                f'fill="{sc["section_bg"]["stroke"]}">{html.escape(l.get("label",""))}</text>'
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

    # 边
    for e in edges:
        a = node_center.get(e.get("source"))
        b = node_center.get(e.get("target"))
        if not a or not b:
            continue
        x1, y1 = a
        x2, y2 = b
        dash = ' stroke-dasharray="8,5"' if e.get("style") == "dashed" else ""
        parts.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{sc["arrow"]["stroke"]}" stroke-width="2.5" marker-end="url(#arrow)"{dash}/>'
        )
        if e.get("label"):
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2 - 12
            lbl = e["label"]
            parts.append(
                f'<rect x="{mx-25}" y="{my-14}" width="{len(lbl)*9+12}" height="20" '
                f'fill="#ffffff" stroke="none"/>'
            )
            parts.append(
                f'<text x="{mx}" y="{my}" text-anchor="middle" font-size="14" '
                f'fill="{sc["text"]["fill"]}">{html.escape(lbl)}</text>'
            )

    # 节点
    for nd in nodes:
        cx, cy = node_center[nd["id"]]
        label = nd.get("label", nd.get("id", ""))
        shape = nd.get("shape", "round")
        fill = sc["primary"]["fill"]
        stroke = sc["primary"]["stroke"]
        # 分组内节点用弱化色
        if nd.get("group"):
            fill = sc["secondary"]["fill"]
            stroke = sc["secondary"]["stroke"]
        w = max(140, len(label) * 10 + 30)
        parts += _node_svg(shape, cx, cy, w, NODE_H, fill, stroke, label, sc)

    # 标题
    if ir.get("title"):
        parts.append(
            f'<text x="{W/2}" y="40" text-anchor="middle" font-size="22" '
            f'font-weight="bold" fill="{sc["text"]["fill"]}">{html.escape(ir["title"])}</text>'
        )

    parts.append("</svg>")
    return "\n".join(parts)


def _node_svg(shape: str, cx: float, cy: float, w: float, h: float,
              fill: str, stroke: str, label: str, sc) -> str:
    x = cx - w / 2
    y = cy - h / 2
    lbl = html.escape(label)
    parts = []
    if shape == "box":
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="4" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    elif shape == "diamond":
        x1, y1, x2, y2, x3, y3, x4, y4 = cx, y, x, cy, cx, y + h, cx + w, cy
        parts.append(f'<polygon points="{x1},{y1} {x2},{y2} {x3},{y3} {x4},{y4}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    elif shape == "cylinder":
        parts.append(f'<rect x="{x}" y="{y+8}" width="{w}" height="{h-8}" rx="4" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        parts.append(f'<ellipse cx="{cx}" cy="{y+8}" rx="{w/2}" ry="{9}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    elif shape == "ellipse":
        parts.append(f'<ellipse cx="{cx}" cy="{cy}" rx="{w/2}" ry="{h/2}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    elif shape == "parallelogram":
        parts.append(f'<polygon points="{x+14},{y} {x+w},{y} {x+w-14},{y+h} {x},{y+h}" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    elif shape == "cloud":
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="28" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2" stroke-dasharray="6,4"/>')
    else:  # round
        parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" '
                     f'fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    parts.append(
        f'<text x="{cx}" y="{cy+5}" text-anchor="middle" font-size="16" '
        f'font-weight="bold" fill="{sc["text"]["fill"]}">{lbl}</text>'
    )
    return parts


def _bbox(ir) -> tuple[float, float, float, float]:
    node_center, _, _, _ = _layout(ir)
    xs = [c[0] for c in node_center.values()]
    ys = [c[1] for c in node_center.values()]
    if not xs or not ys:
        return 0, 0, 600, 400
    xmin, xmax = min(xs) - NODE_W / 2, max(xs) + NODE_W / 2
    ymin, ymax = min(ys) - NODE_H / 2, max(ys) + NODE_H / 2
    return xmin, ymin, xmax, ymax


def render_to_svg(ir: Dict[str, Any], out_path: str, scheme: str = "okabe-ito") -> str:
    svg = build_svg(ir, scheme)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg)
    return out_path


def render_to_pptx(ir: Dict[str, Any], out_path: str, scheme: str = "okabe-ito") -> str:
    """生成原生可编辑 PPTX（python-pptx）：每个节点一个形状、每条边一根连接线。"""
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

    # 边（连接线）
    for e in ir.get("edges", []):
        a = node_center.get(e.get("source"))
        b = node_center.get(e.get("target"))
        if not a or not b:
            continue
        x1, y1 = a
        x2, y2 = b
        conn = slide.shapes.add_connector(
            MSO_CONNECTOR.STRAIGHT,
            ox + Inches(x1 / MM), oy + Inches(y1 / MM),
            ox + Inches(x2 / MM), oy + Inches(y2 / MM),
        )
        conn.line.color.rgb = _hex_to_rgb(sc["arrow"]["stroke"])
        conn.line.width = Pt(2.25)
        if e.get("label"):
            mx = ox + Inches(((x1 + x2) / 2 - 30) / MM)
            my = oy + Inches(((y1 + y2) / 2 - 12) / MM)
            tb = slide.shapes.add_textbox(mx, my, Inches(1.2), Inches(0.4))
            tf = tb.text_frame
            tf.text = e["label"]
            tf.paragraphs[0].font.size = Pt(11)

    # 节点
    for nd in ir.get("nodes", []):
        cx, cy = node_center[nd["id"]]
        label = nd.get("label", nd.get("id", ""))
        shape = nd.get("shape", "round")
        w = max(1.9, len(label) * 0.14 + 0.5)
        h = 0.9
        from pptx.enum.shapes import MSO_SHAPE
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
        fill = sc["secondary"]["fill"] if nd.get("group") else sc["primary"]["fill"]
        sp.fill.solid()
        sp.fill.fore_color.rgb = _hex_to_rgb(fill)
        sp.line.color.rgb = _hex_to_rgb(sc["primary"]["stroke"])
        sp.line.width = Pt(2)
        tf = sp.text_frame
        tf.text = label
        for p in tf.paragraphs:
            p.alignment = PP_ALIGN.CENTER
            p.font.size = Pt(14)
            p.font.bold = True
            p.font.color.rgb = _hex_to_rgb(sc["text"]["fill"])

    # 标题
    if ir.get("title"):
        tb = slide.shapes.add_textbox(Inches(0.6), Inches(0.1), Inches(12), Inches(0.5))
        tf = tb.text_frame
        tf.text = ir["title"]
        tf.paragraphs[0].font.size = Pt(24)
        tf.paragraphs[0].font.bold = True

    prs.save(out_path)
    return out_path


def render_to_emf(ir: Dict[str, Any], out_path: str, scheme: str = "okabe-ito") -> str:
    """IR → EMF（预览用，需 cairosvg+pillow；否则占位+SVG）。"""
    svg = build_svg(ir, scheme)
    try:
        import cairosvg  # type: ignore
        from PIL import Image
        import io

        png = cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=1800)
        im = Image.open(io.BytesIO(png)).convert("RGBA")
        im = im.crop(im.getbbox()) if im.getbbox() else im
        im.save(out_path, "EMF")
    except ImportError:
        with open(out_path, "wb") as f:
            f.write(bytes.fromhex(
                "010000004c000000000000000000000000000000000000000000000000"
                "0000000000000000000000000000000004000000204e45204d46105c00"
                "81760000010100000000000074"
            ))
        svg_path = out_path.rsplit(".", 1)[0] + "_preview.svg"
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg)
    return out_path


def _hex_to_rgb(hex_str: str):
    from pptx.dml.color import RGBColor
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
