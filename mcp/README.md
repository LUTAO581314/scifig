# SciFig MCP Server

论文解析 → 拆解 → 用户确认 → 审计 → 可编辑科研图（SVG/PPTX/PDF/PNG/EMF）的 MCP 工具集。

## 工具

| 工具 | 说明 |
|------|------|
| `prepare_figure` | 默认 Codex 模式：解析文档并返回正文/本地视觉证据；`planner_mode=mcp` 时生成 Diagram IR 草稿 |
| `render_confirmed_figure` | 确认后的 IR → SVG/PPTX/PDF/PNG/EMF；默认把视觉质检交给 Codex |
| `parse_document` | PDF/DOCX/DOC → 结构化 markdown + 页面/嵌入图片证据 |
| `parse_paper` | `parse_document` 的 PDF 兼容别名 |
| `decompose` | 论文文本 + 需求 → Diagram IR JSON（LLM 拆解，含 locks） |
| `validate_ir_tool` | 校验 Diagram IR 合法可渲染 |
| `audit_ir_tool` | 确定性质量审计（passed 闸门） |
| `render_svg` | Diagram IR → SVG 文件 |
| `render_pptx` | Diagram IR → 原生可编辑 PPTX（python-pptx 形状/连接线） |
| `render_emf` | Diagram IR → EMF 文件（预览） |
| `figure_qa` | Diagram IR → PNG + 多模态视觉质量检查 |
| `export_spec` | IR → 带 LOCKED 标记文本（锁定重生成） |

## 安装

```bash
pip install -e .[all]
```

可选依赖：
- 解析：`pip install pdfplumber`（轻量）或 `pip install mineru`（高精度）
- 页面视觉解析：`pip install pymupdf openai`（需要支持图片输入的多模态模型）
- Word 结构化解析：`pip install python-docx`
- Word 页面视觉解析：安装 LibreOffice（用于 DOCX → PDF 页面渲染）
- PPTX 可编辑输出：`pip install python-pptx`
- EMF 预览：`pip install cairosvg pillow`
- PNG/PDF：`pip install cairosvg`

## 配置（国内模型，OpenAI 兼容）

```bash
set SCIFIG_LLM_PROVIDER=qwen     # qwen | glm | deepseek | openai
set SCIFIG_LLM_KEY=sk-xxxx
```

或自定义端点：
```bash
set SCIFIG_LLM_BASE=...
set SCIFIG_LLM_KEY=...
set SCIFIG_LLM_MODEL=...
```

## 配置（国内模型，OpenAI 兼容）

推荐用 `.env`（已自动加载，且被 gitignore，不会上传）：

```bash
# 复制 .env.example 为 .env 并填写
copy .env.example .env
```

配置项：
```
SCIFIG_LLM_PROVIDER=deepseek   # qwen | glm | deepseek | openai
SCIFIG_LLM_BASE=https://newapi.ai.gduf.top/v1
SCIFIG_LLM_KEY=sk-xxxx
SCIFIG_LLM_MODEL=deepseek-v4-flash
SCIFIG_LLM_STREAM=1            # 流式（部分 VLLM 网关必要）

# 多模态模型（推荐单独指定；不填 BASE/KEY 时复用 SCIFIG_LLM_*）
SCIFIG_VISION_BASE=https://api.openai.com/v1
SCIFIG_VISION_KEY=sk-xxxx
SCIFIG_VISION_MODEL=gpt-4o
SCIFIG_PARSE_VISION_MAX_PAGES=12
```

或直接用环境变量注入（MCP 通过 env 传入，优先于 .env）。

## 使用（standalone 测试）

```python
from scifig_mcp.tools.render import render_to_pptx, render_to_svg
from scifig_mcp.tools.audit import audit_ir
from scifig_mcp.diagram_ir import validate_ir

ir = {
    "title": "图1 系统框架",
    "direction": "LR",
    "groups": [{"id": "g1", "label": "输入层"}, {"id": "g2", "label": "处理层"}],
    "lanes": [{"id": "l1", "label": "阶段A"}, {"id": "l2", "label": "阶段B"}],
    "nodes": [
        {"id": "n1", "label": "预处理", "group": "g1", "lane": "l1", "shape": "round"},
        {"id": "n2", "label": "模型", "group": "g2", "lane": "l2", "shape": "box"},
        {"id": "n3", "label": "输出", "group": "g2", "lane": "l2", "shape": "cylinder"},
    ],
    "edges": [
        {"id": "e1", "source": "n1", "target": "n2", "label": "特征", "style": "solid"},
        {"id": "e2", "source": "n2", "target": "n3", "label": "结果", "style": "solid"},
    ],
    "layout": {"canvas_ratio": "4:3"},
    "locks": {"nodes": [], "edges": [], "groups": []},
}

assert not validate_ir(ir)
print(audit_ir(ir))            # passed 闸门
render_to_pptx(ir, "demo.pptx")  # 原生可编辑 PPTX
render_to_svg(ir, "demo.svg")
```

## 在 opencode 中接入

在 opencode 配置中添加 MCP server（通过 env 传 key，或依赖自动加载的 .env）：

```jsonc
{
  "mcp": {
    "scifig": {
      "type": "local",
      "command": ["python", "-m", "scifig_mcp.server"],
      "env": {
        "SCIFIG_LLM_PROVIDER": "deepseek",
        "SCIFIG_LLM_BASE": "https://newapi.ai.gduf.top/v1",
        "SCIFIG_LLM_KEY": "sk-xxxx",
        "SCIFIG_LLM_MODEL": "deepseek-v4-flash",
        "SCIFIG_OUT_DIR": "./loot"
      }
    }
  }
}
```

> 需先把 `mcp/` 加入 Python 路径（`cd mcp && pip install -e .`），或用绝对模块路径。

配合 `skill/` 目录使用，按四阶段工作流执行（文本+视觉解析 → 拆解确认 → 审计 → 出图）。

## Codex 主导的视觉架构

默认 `vision_mode=codex`：MCP 不调用视觉模型 API，只提取 PDF 页面截图或 Word
嵌入图片，并在结果的 `visual_evidence.artifacts` 返回本地文件路径；PDF 解析会跳过
可能自动启动本地 VLM 的 MinerU，改用轻量文本提取。Codex/ChatGPT
负责理解图表、公式和布局，生成 Diagram IR，再调用 `render_confirmed_figure`。

只有独立运行 MCP 的自动视觉解析或自动视觉质检时，才使用
`vision_mode=mcp`、`qa_mode=mcp` 并配置 `SCIFIG_VISION_BASE/KEY/MODEL`。
这组变量是可选的，不是 Codex 正常工作所必需的。

## 外部插件适配

SciFig 不要求把第三方仓库复制进核心代码。将适配器做成普通 Python 模块，
通过 `SCIFIG_PLUGIN_MODULES` 加载即可：

```python
# my_scifig_plugins.py
def register_scifig_plugins(registry):
    from my_docling_adapter import parse_document
    from my_elk_adapter import render_svg
    return registry.override(
        document_parser=parse_document,
        render_svg=render_svg,
        _source=__name__,
    )
```

也可以直接导出 `PLUGIN_OVERRIDES = {"render_svg": render_svg}`。可替换槽位包括
`document_parser`、`planner`、`auditor`、`render_svg`、`render_pptx`、
`render_png`、`render_pdf`、`render_emf` 和 `vision_qa`。工作流结果会返回
`plugins` 字段，记录本次实际使用的实现来源。

### 参考图版式

Diagram IR 节点可选提供 `position: {"x": 180, "y": 240}`。当所有节点都提供
坐标时，渲染器使用手工版式，适合“中心主流程 + 侧边评价/反馈模块”的论文图；
未提供完整坐标时仍使用自动拓扑布局。
