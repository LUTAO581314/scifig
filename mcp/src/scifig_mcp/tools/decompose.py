"""论文拆解：用 LLM 把论文文本 + 需求 → 可作图信息 + Diagram IR(图结构)。

这是整个工作流的核心阶段（阶段2）。产出结构供：
- 对话内确认闸门展示（DIAGRAM IR：节点/边/分组/泳道/方向 + locks）
- 渲染阶段(render_svg/render_pptx/render_emf)消费
"""

from __future__ import annotations

import json

from scifig_mcp.llm.provider import LLM

_SYSTEM = """你是学术论文分析与科研绘图专家。请把论文拆解为"可作图信息"，
严格按给定 JSON schema 输出，不要额外文字。忠实原文，不臆造。"""


def _user_prompt(paper_text: str, requirement: str) -> str:
    req = requirement.strip() or "（用户未指定，请由论文内容自动推荐合适的图）"
    return f"""【论文文本】
{paper_text[:60000]}

【用户作图需求】
{req}

请输出严格 JSON，schema 如下（Diagram IR）：
{{
  "paper_type": {{"type": "method", "confidence": 0.9, "evidence": "摘要出现'我们提出…'"}},
  "parts": [
    {{"id": "p1", "kind": "flow|mechanism|architecture|comparison|structure|data",
      "desc": "内容描述", "source": "原文位置(图1/方法4.2等)", "confidence": 0.9}}
  ],
  "recommended_figures": ["method_overview", "architecture"],
  "figure_irs": [
    {{
      "title": "图1 ...",
      "direction": "LR|TB",
      "groups": [{{"id": "g1", "label": "输入层"}}],
      "lanes": [{{"id": "l1", "label": "阶段A"}}],
      "nodes": [
        {{"id": "n1", "label": "...", "group": "g1", "lane": "l1",
          "shape": "round|box|diamond|cylinder|ellipse|parallelogram|cloud",
          "icon": "关键词(细胞/membrane/DNA/protein/virus 等，生物机制图填充)"}}
      ],
      "edges": [{{"id": "e1", "source": "n1", "target": "n2", "label": "...", "style": "solid|dashed"}}],
      "locks": {{"nodes": [], "edges": [], "groups": []}},
      "caption": "图注建议"
    }}
  ],
  "notes": "拆解说明，供用户确认阅读"
}}
规则：
- 每个图的节点建议 5-10 个、箭头 6-12 个（单栏 ≤5-7 节点/6-10 箭头）
- 每个节点必须有 label；边必须引用存在的节点 id
- 同一功能的节点归入同一 group；需要分阶段的用 lanes
- 只输出 JSON。"""


def decompose_paper(llm: LLM, paper_text: str, requirement: str = "") -> dict:
    raw = llm.chat(_SYSTEM, _user_prompt(paper_text, requirement))
    return extract_json(raw)


def extract_json(text: str) -> dict:
    """从模型输出提取 JSON 对象（容忍 ```json 包裹、前后缀文本、markdown）。"""
    # 优先直接 JSON 解析
    body = text.strip()
    try:
        return json.loads(body)
    except (json.JSONDecodeError, TypeError):
        pass

    # 移除 ``` 代码围栏标记（可能单行或多行包裹）
    body = body.replace("```", " ")

    start = body.find("{")
    end = body.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"无法从 LLM 输出提取 JSON: {text[:200]}")
    return json.loads(body[start : end + 1])
