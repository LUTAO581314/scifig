"""论文解析：PDF → 结构化 markdown。

默认走轻量本地解析（pdfplumber 不可用时提示安装）；若安装了 mineru，
可用 tier 参数调用 MinerU 做高精度解析（图表/公式/多栏）。解析完成后，
默认再用多模态模型分析论文页面截图，补充图表和公式的视觉结构信息。

为了让骨架可独立运行，这里先提供协议骨架：
- parse_paper_file(pdf_path, tier) -> (text, meta)
多模态视觉解析不可用时保留文本结果，并在 meta.visual.warnings 中返回原因。
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Tuple


_VISUAL_HINTS = re.compile(
    r"(?:\bfig(?:ure)?\.?\s*\d*\b|\btable\s*\d*\b|图\s*\d+|表\s*\d+|图表|流程图|架构图)",
    re.IGNORECASE,
)


def parse_paper_file(pdf_path: str, tier: str = "basic",
                     visual: bool = True) -> tuple[str, dict]:
    """解析 PDF 论文为结构化文本。

    Args:
        pdf_path: PDF 绝对路径
        tier: flash/basic/standard/advanced（对应 MinerU 4 档）
        visual: 是否调用多模态模型分析论文中的图、表和公式截图
    Returns:
        (text, meta)
"""
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(f"找不到 PDF: {p}")

    # 优先尝试高精度解析(MinerU)；失败（未装/模型下载问题/时报错）回退轻量 pdfplumber
    try:
        import mineru  # noqa: F401
        if "parse" not in dir(mineru):
            raise ImportError("mineru 无 parse API")
        text, meta = _parse_with_mineru(p, tier)
    except Exception:
        text, meta = _parse_lightweight(p)

    if visual:
        text, visual_meta = _augment_with_visuals(p, text)
        meta.update(visual_meta)
    else:
        meta["visual"] = {"enabled": False, "status": "disabled"}
    return text, meta


def parse_document_file(document_path: str, tier: str = "basic",
                        visual: bool = True) -> tuple[str, dict]:
    """按扩展名解析 PDF、DOCX 或旧版 DOC 文档。

    DOCX 同时走结构化 XML 解析和可选的页面渲染；没有 LibreOffice 时，
    仍会解析段落、表格和嵌入图片，并把可用图片交给多模态模型。
    """
    p = Path(document_path)
    if not p.exists():
        raise FileNotFoundError(f"找不到文档: {p}")
    suffix = p.suffix.lower()
    if suffix == ".pdf":
        return parse_paper_file(str(p), tier=tier, visual=visual)
    if suffix == ".docx":
        return _parse_docx_file(p, visual=visual)
    if suffix == ".doc":
        return _parse_legacy_doc_file(p, visual=visual)
    raise ValueError(f"暂不支持的文档格式: {suffix}（支持 .pdf / .docx / .doc）")


def _iter_docx_blocks(doc):
    """按原始顺序遍历 DOCX 中的段落和表格。"""
    from docx.document import Document as DocxDocument
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.oxml.table import CT_Tbl
    from docx.oxml.text.paragraph import CT_P

    parent = doc.element.body if isinstance(doc, DocxDocument) else doc._tc
    parent_obj = doc if isinstance(doc, DocxDocument) else doc
    for child in parent.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent_obj)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent_obj)


def _table_to_markdown(table) -> str:
    rows: List[List[str]] = []
    for row in table.rows:
        rows.append([
            (cell.text or "").strip().replace("\n", " / ").replace("|", "\\|")
            for cell in row.cells
        ])
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    lines = ["| " + " | ".join(rows[0]) + " |",
             "| " + " | ".join(["---"] * width) + " |"]
    lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return "\n".join(lines)


def _parse_docx_file(path: Path, visual: bool = True) -> tuple[str, dict]:
    try:
        from docx import Document
        from docx.opc.constants import RELATIONSHIP_TYPE as RT
    except ImportError as exc:
        raise RuntimeError("DOCX 解析需要 python-docx：pip install python-docx") from exc

    doc = Document(str(path))
    parts: List[str] = []
    for block in _iter_docx_blocks(doc):
        if block.__class__.__name__ == "Paragraph":
            value = (block.text or "").strip()
            if not value:
                continue
            style_name = str(getattr(getattr(block, "style", None), "name", ""))
            match = re.search(r"Heading\s*(\d+)", style_name, re.IGNORECASE)
            prefix = "#" * min(int(match.group(1)), 6) + " " if match else ""
            parts.append(prefix + value)
        else:
            table_md = _table_to_markdown(block)
            if table_md:
                parts.append(table_md)

    images: List[Dict[str, Any]] = []
    for rel in doc.part.rels.values():
        if rel.reltype == RT.IMAGE:
            target = rel.target_part
            images.append({
                "id": rel.rId,
                "bytes": target.blob,
                "mime_type": getattr(target, "content_type", "image/png"),
            })

    text = "\n\n".join(parts).strip()
    if not text:
        text = "# 未提取到正文\n"
    meta: Dict[str, Any] = {
        "stem": path.stem,
        "engine": "python-docx",
        "document_type": "docx",
        "images": len(images),
    }

    if not visual:
        meta["visual"] = {"enabled": False, "status": "disabled"}
        return text, meta

    visual_text, visual_meta = _augment_docx_with_visuals(path, text, images)
    meta.update(visual_meta)
    return visual_text, meta


def _convert_office_to_pdf(path: Path) -> tuple[Path, Path] | None:
    """使用 LibreOffice 将 DOC/DOCX 渲染为 PDF，供页面视觉解析。"""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    temp_dir = Path(tempfile.mkdtemp(prefix="scifig-office-"))
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir",
             str(temp_dir), str(path)],
            check=True, capture_output=True, timeout=180,
        )
        output = temp_dir / f"{path.stem}.pdf"
        if output.exists():
            return output, temp_dir
    except (OSError, subprocess.SubprocessError):
        pass
    shutil.rmtree(temp_dir, ignore_errors=True)
    return None


def _parse_legacy_doc_file(path: Path, visual: bool = True) -> tuple[str, dict]:
    converted = _convert_office_to_pdf(path)
    if converted is None:
        raise RuntimeError(
            "旧版 .doc 需要 LibreOffice 才能解析。请安装 LibreOffice，"
            "或先另存为 .docx/.pdf。"
        )
    pdf_path, temp_dir = converted
    try:
        text, meta = parse_paper_file(str(pdf_path), visual=visual)
        meta["stem"] = path.stem
        meta["document_type"] = "doc"
        return text, meta
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _augment_docx_with_visuals(path: Path, text: str,
                               images: List[Dict[str, Any]]) -> tuple[str, dict]:
    """优先分析 Word 渲染页；没有办公渲染器时分析嵌入图片。"""
    rendered = _convert_office_to_pdf(path)
    if rendered is not None:
        pdf_path, temp_dir = rendered
        try:
            visual_text, visual_meta = _augment_with_visuals(pdf_path, text)
            visual_meta["visual"]["source"] = "rendered_pages"
            return visual_text, visual_meta
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    visual_meta: Dict[str, Any] = {
        "visual": {"enabled": True, "status": "pending", "source": "embedded_images",
                   "pages": [], "figures": 0, "tables": 0, "warnings": []}
    }
    try:
        from scifig_mcp.llm.provider import get_model_config
        get_model_config("multimodal")
        from scifig_mcp.tools.vision import analyze_image_bytes
    except Exception as exc:
        visual_meta["visual"]["status"] = "not_configured"
        visual_meta["visual"]["warnings"].append(str(exc))
        return text, visual_meta

    if not images:
        visual_meta["visual"]["status"] = "no_embedded_images"
        visual_meta["visual"]["warnings"].append(
            "未找到嵌入图片；安装 LibreOffice 后可按页面进行视觉解析。"
        )
        return text, visual_meta

    analyses: List[Dict[str, Any]] = []
    try:
        for index, item in enumerate(images, start=1):
            result = analyze_image_bytes(
                item["bytes"],
                f"请分析这张 Word 文档中的第 {index} 个嵌入图像。识别它是否是科研图、表格或公式，"
                "并严格返回 JSON：{\"type\":\"figure/table/equation/other\","
                "\"caption\":\"\",\"visual_summary\":\"\",\"uncertain\":false}",
                context="这是论文或科研报告中的嵌入图像，请不要臆造看不清的内容。",
                mime_type=item["mime_type"],
            )
            parsed = _extract_json_object(result.get("answer", ""))
            if not isinstance(parsed, dict):
                parsed = {"raw": result.get("answer", "")}
            parsed["image"] = index
            analyses.append(parsed)
            if parsed.get("type") == "figure":
                visual_meta["visual"]["figures"] += 1
            if parsed.get("type") == "table":
                visual_meta["visual"]["tables"] += 1
    except Exception as exc:
        visual_meta["visual"]["status"] = "error"
        visual_meta["visual"]["warnings"].append(str(exc))
        return text, visual_meta

    visual_meta["visual"]["status"] = "ok"
    section = ["## 图表与公式视觉解析", "",
               "以下内容来自多模态模型对 Word 嵌入图片的辅助识别，请结合原文复核：", "",
               "```json", json.dumps(analyses, ensure_ascii=False, indent=2), "```"]
    return text.rstrip() + "\n\n" + "\n".join(section) + "\n", visual_meta


def _select_visual_pages(pdf_path: Path, max_pages: int) -> List[int]:
    """优先选择包含图表标题的页面，避免把整篇论文逐页发送给模型。"""
    import fitz  # type: ignore

    pages: List[int] = []
    all_pages = os.environ.get("SCIFIG_PARSE_VISION_ALL_PAGES", "0") == "1"
    with fitz.open(str(pdf_path)) as doc:
        if all_pages:
            return list(range(min(len(doc), max_pages)))
        for index, page in enumerate(doc):
            page_text = page.get_text("text") or ""
            has_embedded_images = bool(page.get_images(full=True))
            if _VISUAL_HINTS.search(page_text) or has_embedded_images:
                pages.append(index)
            if len(pages) >= max_pages:
                break
        # 没有可检索文本时至少看首页，避免扫描件完全跳过视觉解析。
        if not pages and len(doc):
            pages.append(0)
    return pages


def _extract_json_object(text: str) -> Any:
    """容忍多模态模型返回代码围栏或少量解释文字。"""
    body = (text or "").strip().replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(body)
    except (TypeError, json.JSONDecodeError):
        start, end = body.find("{"), body.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(body[start:end + 1])
            except json.JSONDecodeError:
                pass
    return {"raw": text}


def _visual_question(page_number: int) -> str:
    return f"""请分析这篇论文第 {page_number} 页的页面截图，重点识别图、表和公式。
不要臆造看不清的内容；无法确定的字段填 null，并返回严格 JSON：
{{
  "figures": [{{"id": "Figure 1", "caption": "", "type": "流程图/机制图/架构图/曲线图/其他", "visual_summary": "", "key_entities": [], "uncertain": false}}],
  "tables": [{{"id": "Table 1", "caption": "", "columns": [], "key_findings": [], "uncertain": false}}],
  "equations": [{{"label": "", "meaning": "", "uncertain": false}}],
  "page_notes": ""
}}
只输出 JSON。"""


def _augment_with_visuals(pdf_path: Path, text: str) -> Tuple[str, Dict[str, Any]]:
    """把论文页面截图交给多模态模型，并把结果追加到解析 Markdown。"""
    meta: Dict[str, Any] = {
        "visual": {"enabled": True, "status": "pending", "pages": [],
                   "figures": 0, "tables": 0, "warnings": []}
    }
    visual_meta = meta["visual"]

    try:
        from scifig_mcp.llm.provider import get_model_config
        get_model_config("multimodal")
    except Exception as exc:
        visual_meta["status"] = "not_configured"
        visual_meta["warnings"].append(str(exc))
        return text, meta

    try:
        import fitz  # type: ignore
        from scifig_mcp.tools.vision import analyze_image_bytes
    except Exception as exc:
        visual_meta["status"] = "dependency_missing"
        visual_meta["warnings"].append(
            f"页面视觉解析需要 PyMuPDF 和 openai 依赖: {exc}"
        )
        return text, meta

    try:
        max_pages = max(1, int(os.environ.get("SCIFIG_PARSE_VISION_MAX_PAGES", "12")))
        page_indexes = _select_visual_pages(pdf_path, max_pages)
        visual_meta["pages"] = [i + 1 for i in page_indexes]
        analyses: List[Dict[str, Any]] = []
        with fitz.open(str(pdf_path)) as doc:
            for page_index in page_indexes:
                page = doc[page_index]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                page_png = pix.tobytes("png")
                page_text = (page.get_text("text") or "")[:3000]
                result = analyze_image_bytes(
                    page_png,
                    _visual_question(page_index + 1),
                    context=("这是论文页面截图。页面文字摘录如下：\n" + page_text
                             if page_text else "这是论文页面截图。"),
                )
                parsed = _extract_json_object(result.get("answer", ""))
                if not isinstance(parsed, dict):
                    parsed = {"raw": result.get("answer", "")}
                parsed["page"] = page_index + 1
                analyses.append(parsed)
                visual_meta["figures"] += len(parsed.get("figures", []) or [])
                visual_meta["tables"] += len(parsed.get("tables", []) or [])

        if not analyses:
            visual_meta["status"] = "no_candidates"
            return text, meta

        visual_meta["status"] = "ok"
        section = ["## 图表与公式视觉解析", ""]
        section.append("以下内容来自多模态模型对论文页面截图的辅助识别，请结合原文复核：")
        section.append("")
        section.append("```json")
        section.append(json.dumps(analyses, ensure_ascii=False, indent=2))
        section.append("```")
        return text.rstrip() + "\n\n" + "\n".join(section) + "\n", meta
    except Exception as exc:
        visual_meta["status"] = "error"
        visual_meta["warnings"].append(str(exc))
        return text, meta


def _parse_with_mineru(p: Path, tier: str) -> tuple[str, dict]:
    """调用 MinerU 解析（mineru>=4，顶层 parse() 函数）。"""
    import mineru

    # tier 映射到 mineru 支持的枚举字符串
    tier_map = {"flash": "flash", "basic": "standard", "standard": "standard", "advanced": "advanced"}
    try:
        result = mineru.parse(str(p), tier=tier_map.get(tier, "standard"), ocr_mode="auto")
    except TypeError:
        result = mineru.parse(str(p))

    # 4.x 中 markdown / export_pages 均为方法
    if callable(getattr(result, "markdown", None)):
        text = result.markdown() or ""
    else:
        text = result.markdown or ""
    try:
        page_count = len(result.export_pages()) if callable(getattr(result, "export_pages", None)) else None
    except Exception:
        page_count = None

    meta = {"stem": p.stem, "engine": "mineru", "tier": tier, "pages": page_count}
    return text, meta


def _parse_lightweight(p: Path) -> tuple[str, dict]:
    """轻量解析：尝试 pdfplumber 提取文本；无工具时给出引导。"""
    try:
        import pdfplumber  # type: ignore

        parts: list[str] = []
        with pdfplumber.open(str(p)) as pdf:
            for i, page in enumerate(pdf.pages):
                t = page.extract_text() or ""
                parts.append(f"## Page {i+1}\n\n{t}")
        meta = {"stem": p.stem, "engine": "pdfplumber", "pages": len(parts)}
        return "\n\n".join(parts), meta
    except ImportError:
        raise RuntimeError(
            "本机未安装解析后端。二选一：\n"
            "  1) pip install pdfplumber（轻量文本提取）\n"
            "  2) pip install mineru（高精度，图表/公式/多栏）\n"
            "生产建议优先接入 MinerU，见 README。"
        )
