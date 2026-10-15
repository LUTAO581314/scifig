"""SciFig MCP server：论文解析 → 拆解(IR) → 可编辑科研图(SVG/PPTX/EMF)。

工具清单：
- parse_paper    : PDF → 结构化 markdown（可选，复用 MinerU）
- decompose      : 论文文本 + 需求 → Diagram IR JSON（LLM 拆解，含 locks）
- validate_ir    : 校验 Diagram IR 是否合法可渲染
- audit_ir       : 确定性质量审计（越界/密度/孤立节点等），passed gate
- render_svg     : Diagram IR → SVG 文件
- render_pptx    : Diagram IR → PPTX 文件（python-pptx 原生可编辑形状/连接线）
- render_emf     : Diagram IR → EMF 文件（预览）
- figure_qa      : 视觉质检（本地 Ollama VL 模型）：渲染→严格五项检查→问题清单
- vision_describe: 让本地 VL 模型读任意本地图并回答（深检）
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from fastmcp import FastMCP

from scifig_mcp.diagram_ir import validate_ir, ir_to_json
from scifig_mcp.llm.provider import get_llm
from scifig_mcp.tools.audit import audit_ir
from scifig_mcp.tools.decompose import decompose_paper
from scifig_mcp.tools.parse import parse_paper_file
from scifig_mcp.tools.render import render_to_svg, render_to_pptx, render_to_emf

mcp = FastMCP("scifig-mcp")

OUT_DIR = Path(os.environ.get("SCIFIG_OUT_DIR", "./loot")).resolve()


def _out(name: str, ext: str) -> Path:
    out = OUT_DIR / f"{name}.{ext}"
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


@mcp.tool()
def parse_paper(pdf_path: str, tier: str = "basic") -> str:
    """把 PDF 论文解析成结构化 markdown（标题/摘要/方法/图表/公式）。

    Args:
        pdf_path: 论文 PDF 的绝对路径
        tier: 解析质量 flash/basic/standard/advanced（默认 basic）
    Returns:
        结构化 markdown 文本（写入 loot/, 返回路径+摘要）
    """
    text, meta = parse_paper_file(pdf_path, tier=tier)
    out = OUT_DIR / "parsed" / f"{meta.get('stem','paper')}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    return json.dumps({"path": str(out), "chars": len(text), "meta": meta}, ensure_ascii=False)


@mcp.tool()
def decompose(paper_text: str, requirement: str = "") -> str:
    """用 LLM 拆解论文，产出可作图信息 + Diagram IR（含 locks）。

    Args:
        paper_text: 论文文本（markdown 或纯文本）
        requirement: 用户作图需求描述（可为空，自动推荐）
    Returns:
        JSON：{paper_type, parts, recommended_figures, figure_irs, notes}
    """
    llm = get_llm()
    result = decompose_paper(llm, paper_text, requirement)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def validate_ir_tool(ir: dict) -> str:
    """校验 Diagram IR 是否合法可渲染（节点/边引用、shape、direction、locks）。

    Args:
        ir: Diagram IR JSON 对象
    Returns:
        JSON：{valid, errors[]}
    """
    errors = validate_ir(ir)
    return json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False)


@mcp.tool()
def audit_ir_tool(ir: dict) -> str:
    """对 Diagram IR 做确定性质量审计，返回 passed 闸门。

    Args:
        ir: Diagram IR JSON 对象
    Returns:
        JSON：{passed, hard_failure_count, warning_count, findings[]}
    """
    return json.dumps(audit_ir(ir), ensure_ascii=False, indent=2)


@mcp.tool()
def render_svg(ir: dict, out_name: str = "figure", scheme: str = "okabe-ito") -> str:
    """把确认后的 Diagram IR 渲染成 SVG 文件。

    Args:
        ir: Diagram IR JSON
        out_name: 输出文件基本名
        scheme: 配色主题 (okabe-ito/nature/ieee/vivid/pastel)
    Returns:
        SVG 文件绝对路径
    """
    out = _out(out_name, "svg")
    render_to_svg(ir, str(out), scheme)
    return str(out)


@mcp.tool()
def render_pptx(ir: dict, out_name: str = "figure", scheme: str = "okabe-ito") -> str:
    """把 Diagram IR 渲染成原生可编辑 PPTX（每个节点一个形状、每条边一根连接线）。

    Args:
        ir: Diagram IR JSON
        out_name: 输出文件基本名
        scheme: 配色主题
    Returns:
        PPTX 文件绝对路径
    """
    out = _out(out_name, "pptx")
    render_to_pptx(ir, str(out), scheme)
    return str(out)


@mcp.tool()
def render_emf(ir: dict, out_name: str = "figure", scheme: str = "okabe-ito") -> str:
    """把 Diagram IR 渲染成 EMF（预览用，需 cairosvg；否则占位+SVG）。

    Args:
        ir: Diagram IR JSON
        out_name: 输出文件基本名
        scheme: 配色主题
    Returns:
        EMF 文件绝对路径
    """
    out = _out(out_name, "emf")
    render_to_emf(ir, str(out), scheme)
    return str(out)


@mcp.tool()
def export_spec(ir: dict) -> str:
    """把 Diagram IR 序列化成带 [LOCKED] 标记的文本（供'人编辑后带锁重生成'）。

    Args:
        ir: Diagram IR JSON
    Returns:
        可读文本，用于确认展示与锁定重生成
    """
    from scifig_mcp.diagram_ir import format_ir_for_regeneration
    return format_ir_for_regeneration(ir)


@mcp.tool()
def figure_qa(ir: dict, question: str = "", context: str = "",
              scheme: str = "okabe-ito", out_name: str = "figure") -> str:
    """视觉质检（本地 Ollama 视觉模型）：渲染 IR 成 PNG 后严格检查，返回问题清单。

    默认执行发表质量五项：数据流方向/连线连接与交叉/文字截断出框/
    标题与分组标签可读性/距发表质量的差距。有问题先修 IR 或渲染，再复检。

    Args:
        ir: Diagram IR JSON
        question: 自定义质检问题（默认发表质量五项清单）
        context: 论文背景描述（带上下文可显著提高判断准确性）
        scheme: 配色主题
        out_name: 质检 PNG 输出基本名（写入 loot/）
    Returns:
        JSON：{ok, answer, png_path, usage}
    """
    from scifig_mcp.tools.vision import figure_qa as _qa
    result = _qa(ir, question=question, context=context, scheme=scheme,
                 out_dir=str(OUT_DIR), out_name=out_name)
    return json.dumps(result, ensure_ascii=False, indent=2)


@mcp.tool()
def vision_describe(image_path: str, question: str = "请详细描述这张图的内容",
                    context: str = "") -> str:
    """让本地视觉模型直接读一张本地图并回答问题（深检任意图，含论文原图）。

    Args:
        image_path: 本地图片绝对路径（png/jpg）
        question: 要回答的问题
        context: 背景描述（提高判断准确性）
    Returns:
        JSON：{ok, image_path, answer, usage}
    """
    from scifig_mcp.tools.vision import vision_describe as _vd
    result = _vd(image_path, question=question, context=context)
    return json.dumps(result, ensure_ascii=False, indent=2)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
