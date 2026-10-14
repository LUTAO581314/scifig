# SciFig MCP Server

论文解析 → 拆解 → 可编辑科研图（SVG + EMF）的 MCP 工具集。

## 工具

| 工具 | 说明 |
|------|------|
| `parse_paper` | PDF → 结构化 markdown（复用 MinerU / pdfplumber） |
| `decompose` | 论文文本 + 需求 → `figure_spec` JSON（LLM 拆解） |
| `render_svg` | `figure_spec` → SVG 文件 |
| `render_emf` | `figure_spec` → EMF 文件（PPT/Word 直接插入可编辑） |

## 安装

```bash
pip install -e .
```

可选依赖：
- 解析：`pip install pdfplumber`（轻量）或 `pip install mineru`（高精度）
- EMF 转换：`pip install cairosvg pillow`

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

## 使用（standalone 测试）

```python
from scifig_mcp.tools.render import build_svg, render_to_svg

spec = {
    "title": "图1 系统框架",
    "direction": "LR",
    "groups": [{"name": "输入层", "color": "blues"}],
    "nodes": [
        {"id": "n1", "label": "预处理", "group": "输入层"},
        {"id": "n2", "label": "模型", "group": ""},
        {"id": "n3", "label": "输出", "group": ""},
    ],
    "edges": [
        {"from": "n1", "to": "n2", "label": "特征"},
        {"from": "n2", "to": "n3", "label": "结果"},
    ],
    "caption": "示例图注",
}
render_to_svg(spec, "demo.svg")
```

## 在 opencode 中接入

在 opencode 配置中添加 MCP server：

```jsonc
{
  "mcp": {
    "scifig": {
      "type": "local",
      "command": ["python", "-m", "scifig_mcp.server"],
      "env": {
        "SCIFIG_LLM_PROVIDER": "qwen",
        "SCIFIG_LLM_KEY": "sk-xxxx",
        "SCIFIG_OUT_DIR": "./loot"
      }
    }
  }
}
```

配合 `skill/` 目录使用，按四阶段工作流执行。
