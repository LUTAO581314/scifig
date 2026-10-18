"""视觉能力：Diagram IR / 本地图像 → OpenAI 兼容多模态模型。

默认问题是"发表质量五项"（方向/连线/截断/标签/差距），可带论文背景 context
——模型端点由 ``SCIFIG_VISION_*`` 或统一的 ``SCIFIG_LLM_*`` 配置。
"""

from __future__ import annotations

import base64
import os
from typing import Any, Dict, List

from scifig_mcp.llm.provider import get_model_config
from scifig_mcp.tools.render import build_svg

VISION_TIMEOUT = int(os.environ.get("SCIFIG_VISION_TIMEOUT", "300"))

DEFAULT_QA_PROMPT = (
    "请严格质检这张科研图并逐条回答（只列问题，不泛泛夸奖）: "
    "1)数据流方向是什么，起点/终点节点是什么 "
    "2)连线箭头是否正确连接，有无断线或交叉混乱 "
    "3)有无节点重叠、文字被截断或超出框外 "
    "4)标题和分组/泳道标签是否完整可读 "
    "5)距离论文插图发表质量还差什么，指出最该改的1-2处"
)


def _chat(messages: List[Dict], model: str = None, base: str = None,
          key: str = None, timeout: int = None) -> Dict[str, Any]:
    """通过 OpenAI 兼容接口发起一次多模态请求。"""
    from openai import OpenAI

    cfg = get_model_config("multimodal")
    client = OpenAI(base_url=base or cfg.base, api_key=key or cfg.key,
                    timeout=timeout or VISION_TIMEOUT)
    resp = client.chat.completions.create(
        model=model or cfg.model, messages=messages, temperature=0.1
    )
    usage = {}
    if resp.usage is not None:
        usage = {
            "prompt_tokens": getattr(resp.usage, "prompt_tokens", None),
            "completion_tokens": getattr(resp.usage, "completion_tokens", None),
        }
    return {"answer": resp.choices[0].message.content or "", "usage": usage}


def _svg_to_png_bytes(svg: str, width: int = 1800) -> bytes:
    import cairosvg

    return cairosvg.svg2png(bytestring=svg.encode("utf-8"), output_width=width)


def _image_blocks(b64: str, question: str, mime_type: str = "image/png") -> List[Dict]:
    return [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64," + b64}},
    ]


def _build_messages(image_bytes: bytes, question: str, context: str = "",
                    mime_type: str = "image/png") -> List[Dict]:
    messages: List[Dict] = []
    if context and context.strip():
        messages.append({"role": "user", "content": context.strip()})
    messages.append({
        "role": "user",
        "content": _image_blocks(base64.b64encode(image_bytes).decode(), question, mime_type),
    })
    return messages


def analyze_image_bytes(image_bytes: bytes, question: str,
                        context: str = "", mime_type: str = "image/png") -> Dict[str, Any]:
    """让多模态模型分析内存中的图片，供论文图表解析复用。"""
    if not image_bytes:
        raise ValueError("图片内容为空")
    try:
        return _chat(_build_messages(image_bytes, question, context, mime_type))
    except Exception as e:
        raise RuntimeError(
            f"多模态模型不可用: {e}. "
            "请配置 SCIFIG_VISION_BASE/KEY/MODEL，或复用 SCIFIG_LLM_BASE/KEY/MODEL，"
            "并确认所选模型支持图片输入。"
        ) from e


def figure_qa(ir: Dict, question: str = "", context: str = "",
              scheme: str = "okabe-ito", out_dir: str = None,
              out_name: str = "figure") -> Dict[str, Any]:
    """IR → SVG → PNG（落盘）→ VL 严格质检 → 问题清单。"""
    svg = build_svg(ir, scheme)
    png = _svg_to_png_bytes(svg)

    png_path = None
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        png_path = os.path.join(out_dir, f"{out_name}_qa.png")
        with open(png_path, "wb") as f:
            f.write(png)

    q = (question or "").strip() or DEFAULT_QA_PROMPT
    try:
        result = _chat(_build_messages(png, q, context))
    except Exception as e:
        raise RuntimeError(
            f"多模态模型不可用: {e}. "
            "请配置 SCIFIG_VISION_BASE/KEY/MODEL，或复用 SCIFIG_LLM_BASE/KEY/MODEL，"
            "并确认所选模型支持图片输入。"
        ) from e
    return {"ok": True, "png_path": png_path, **result}


def vision_describe(image_path: str, question: str = "请详细描述这张图的内容",
                    context: str = "") -> Dict[str, Any]:
    """让多模态模型直接读一张本地图并回答问题（深检任意图）。"""
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图片不存在: {image_path}")
    with open(image_path, "rb") as f:
        png = f.read()
    try:
        result = _chat(_build_messages(png, question, context))
    except Exception as e:
        raise RuntimeError(
            f"多模态模型不可用: {e}. "
            "请配置 SCIFIG_VISION_BASE/KEY/MODEL，或复用 SCIFIG_LLM_BASE/KEY/MODEL，"
            "并确认所选模型支持图片输入。"
        ) from e
    return {"ok": True, "image_path": image_path, **result}
