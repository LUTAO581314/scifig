# SciFig — 学术论文 → 可编辑科研图

把**一篇学术论文（PDF/DOCX/DOC + 作图需求）**自动拆解，并生成**可编辑矢量科研图**（机制图/流程图/架构图/示意图），输出 **SVG / PPTX / PNG / PDF / EMF**。PPTX 由 python-pptx 生成**原生可编辑 OOXML 形状与连接线**；SVG/PPTX 是编辑主格式，PNG/PDF 用于预览和投稿。

覆盖全论文类型，`skill + MCP server` 双形态交付，面向国内大模型生态（Qwen / GLM / DeepSeek）。

## 核心思想

**先拆解、确认无问题、再出图。可编辑对象，而非位图。**

四条设计原则：
1. **按论文类型分类**选图示（方法/机制/评测/综述/理论/工程/数据 × 11 种图）
2. **拆解确认闸门**：LLM 拆解出 **Diagram IR**（节点/边/分组/泳道/方向 + locks），你在对话内确认或修改后才出图
3. **可编辑对象交付**：PPTX 原生可编辑形状/连接线（含箭头）+ SVG；PNG/PDF/EMF 用于预览与投稿
4. **多端接入国内模型**：OpenAI 兼容接口，一次配置通吃 Qwen / GLM / DeepSeek
5. **机制图图标库**：集成 Bioicons（~2800 个开源科研图标：细胞/膜/蛋白/DNA/病毒/仪器），AI 自动按节点语义配图标

## 工作流

```
用户只和 ChatGPT 对话
   │
   ▼
ChatGPT 调用 SciFig MCP：prepare_figure
   │
   ▼
MCP 工作流编排器
   ├─ 文档插件：MinerU/pdfplumber/python-docx + 页面级多模态视觉
   ├─ 规划插件：OpenAI-compatible LLM → FigureSpec/Diagram IR
   ├─ 确定性校验：validate + audit（硬失败阻断）
   └─ 返回待确认草稿、证据来源和修改建议
   │  [用户确认/修改 IR 后]
   ▼
ChatGPT 调用 SciFig MCP：render_confirmed_figure
   │
   ├─ SVG / PPTX / PDF / PNG / EMF 渲染插件
   ├─ 多模态视觉质检插件（可选）
   └─ 返回可编辑科研图、预览和下一轮修改建议
```

SciFig 只保留统一协议、确认闸门、审计和插件适配层；解析、布局、图标、
渲染和视觉模型都可以替换为成熟仓库或外部服务。

外部适配器通过 `SCIFIG_PLUGIN_MODULES` 加载，不需要修改 MCP 核心；每次工作流
结果会记录实际使用的插件来源。

## 目录结构

```
skill/                 # opencode skill（主工作流指令 + 参考资料）
  SKILL.md               # 四阶段工作流指令
  references/            # paper-types / figure-types / design-theory / prompt-templates
mcp/                   # MCP server（Python, FastMCP）
  src/scifig_mcp/
    server.py             # MCP 入口：高层工作流 + 低级插件工具
    workflow.py            # prepare → confirm → render → QA 编排器
    plugins.py             # 可替换能力注册表
    diagram_ir.py         # Diagram IR schema + 校验 + 锁定重生成序列化
    palette.py            # 8-role 语义配色 + 5 套预设（Okabe-Ito/Nature/IEEE/Vivid/Pastel）
    llm/provider.py       # 国内模型抽象（Qwen/GLM/DeepSeek, OpenAI 兼容）
    iconlib.py            # 机制图图标库（Bioicons 搜索/获取/内联）
    tools/parse.py        # 论文解析（PDF/DOCX/DOC + 页面多模态视觉）
    tools/decompose.py    # LLM 拆解 → Diagram IR
    tools/render.py       # SVG / PPTX / PNG / PDF / EMF 渲染
    tools/audit.py        # 确定性质量审计
tests/                  # pytest 单元测试（62 个）
examples/              # 示例
loot/                  # 输出目录（SVG/PPTX/EMF/解析结果）
```

## 可编辑目标 & 图标

- **PPTX**：每个节点一个原生可编辑形状，每条边一根连接线 + 末端箭头，虚线支持。PPT 内直接改。
- **SVG / EMF**：矢量，可插入 Word/PPT 二次编辑。
- **机制图图标**：节点加 `"icon":"cell"`（或 `{"name":"DNA","category":"Nucleic_acids"}`），
  自动从 Bioicons 匹配并嵌入。本地库配置：
  ```bash
  # clone 图标库（一次）
  git clone --depth 1 https://github.com/duerrsimon/bioicons.git <某目录>
  # 指定给 SciFig
  set SCIFIG_BIOICONS_DIR=<该目录>
  ```
  未配置时自动回退远程下载（需访问 GitHub）。

## 快速开始

### 1. 安装 MCP server

```bash
cd mcp
pip install -e .[all]
# 解析：pip install pdfplumber  →或→  pip install mineru（高精度）
# PPTX 可编辑输出：pip install python-pptx
# EMF 预览：pip install cairosvg pillow
# 页面视觉解析：pip install pymupdf openai
```

### 2. 配置国内模型（任选一）

```bash
# 方式A：指定 provider（Qwen 为例）
set SCIFIG_LLM_PROVIDER=qwen
set SCIFIG_LLM_KEY=sk-xxxx
# 方式B：自定义端点
set SCIFIG_LLM_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1
set SCIFIG_LLM_KEY=sk-xxxx
set SCIFIG_LLM_MODEL=qwen-max
```

论文图表解析和出图质检使用支持图片输入的多模态模型。可单独配置：
```bash
set SCIFIG_VISION_BASE=https://api.openai.com/v1
set SCIFIG_VISION_KEY=sk-xxxx
set SCIFIG_VISION_MODEL=gpt-4o
```
未设置 `SCIFIG_VISION_*` 时会复用 `SCIFIG_LLM_*`，但模型必须支持图片输入。

### 3. 在 opencode 使用

skill 位于 `skill/`，MCP server 在 `mcp/`。详见 `mcp/README.md`。

### 4. 在 Codex 使用

仓库已包含项目级 `.codex/config.toml`。在仓库根目录安装依赖后，信任该项目，
Codex 会读取 `scifig` MCP 配置；密钥通过本机环境变量传入，不会写入仓库。

```bash
cd mcp
pip install -e .[all]
codex mcp list
```

看到 `scifig` 为 `enabled` 即表示 Codex 已发现该 MCP。首次使用时可在 Codex
TUI 中执行 `/mcp` 查看工具，或直接调用 `prepare_figure`。

## MCP 工具

| 工具 | 说明 |
|------|------|
| `prepare_figure` | 默认 Codex 模式：文档解析 → 正文/视觉证据；可选 `planner_mode=mcp` 自动生成草稿 |
| `render_confirmed_figure` | 确认后的 IR → 可编辑图 + QA 建议 |
| `parse_document` | PDF/DOCX/DOC → 结构化 markdown + 图表/公式多模态解析 |
| `parse_paper` | `parse_document` 的 PDF 兼容别名 |
| `decompose` | 论文 + 需求 → Diagram IR JSON（LLM 拆解） |
| `validate_ir_tool` | 校验 IR 合法可渲染 |
| `audit_ir_tool` | 确定性质量审计（passed 闸门） |
| `render_svg` | IR → SVG |
| `render_pptx` | IR → 原生可编辑 PPTX |
| `render_emf` | IR → EMF（预览） |
| `figure_qa` | 渲染结果 → 多模态视觉质检 |
| `export_spec` | IR → 带 LOCKED 标记文本（锁定重生成） |

## 路线图

- [x] 高层工作流编排 + 用户确认闸门 + 插件注册表
- [x] Diagram IR schema + 校验 + locks 锁定重生成
- [x] PPTX 原生可编辑渲染器（含箭头 + 虚线）
- [x] 8-role 语义配色 + 5 套预设
- [x] 确定性质量审计
- [x] 机制图图标库集成（Bioicons ~2800 图标）
- [ ] MinerU 高精度解析接入（已装，待批量优化）
- [ ] draw.io 实时画布 MCP（二期）
- [ ] Servier Medical Art 医疗图标接入

## License

MIT

