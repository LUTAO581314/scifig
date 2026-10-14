"""论文解析：PDF → 结构化 markdown。

默认走轻量本地解析（pdfplumber 不可用时退化为占位）；若安装了 mineru，
可用 tier 参数调用 MinerU 做高精度解析（图表/公式/多栏）。

为了让骨架可独立运行，这里先提供协议骨架：
- parse_paper_file(pdf_path, tier) -> (text, meta)
首期实现返回"待接入解析后端"的引导信息，真正的 MinerU 接入见注释。
"""

from __future__ import annotations

from pathlib import Path


def parse_paper_file(pdf_path: str, tier: str = "basic") -> tuple[str, dict]:
    """解析 PDF 论文为结构化文本。

    Args:
        pdf_path: PDF 绝对路径
        tier: flash/basic/standard/advanced（对应 MinerU 4 档）
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
        return _parse_with_mineru(p, tier)
    except Exception:
        return _parse_lightweight(p)


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
