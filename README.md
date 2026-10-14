# SciFig — 学术论文 → 可编辑科研图

把**一篇学术论文（PDF + 作图需求）**自动拆解，并生成**可编辑矢量科研图**（机制图/流程图/架构图/示意图），输出 **SVG + EMF**，可直接插入 PowerPoint / Word 二次编辑。

覆盖全论文类型，`skill + MCP server` 双形态交付，面向国内大模型生态（Qwen / GLM / DeepSeek）。

## 核心思想

**先拆解、确认无问题、再出图。可编辑矢量，而非位图。**

四条设计原则：
1. **按论文类型分类**选图示（方法/机制/评测/综述/理论/工程/数据 → 对应 11 种图）
2. **拆解确认闸门**：LLM 拆解出可作图信息，你在对话内确认或修改后才出图
3. **可编辑矢量交付**：SVG + EMF，EMF 进 PPT/Word 右键"转换为形状"即是可编辑对象
4. **多端接入国内模型**：OpenAI 兼容接口，一次配置通吃 Qwen / GLM / DeepSeek

## 工作流

```
论文PDF + 需求
   │ ① 解析(可复用 MinerU) ─→ 结构化 markdown
   ▼
拆解(LLM 分类决策树) ─→ figure_spec JSON + 推荐图清单
   │  [对话内确认闸门：确认/修改后继续]
   ▼
渲染(可编辑矢量) ─→ SVG + EMF（PPT/Word 直接可编辑）
   ▼
交付：SVG + EMF + 预览 PNG + 图注建议
```

## 目录结构

```
skill/                 # opencode skill（主工作流指令 + 参考资料）
  SKILL.md               # 四阶段工作流指令
  references/            # paper-types / figure-types / design-theory / prompt-templates
mcp/                   # MCP server（Python, FastMCP）
  src/scifig_mcp/
    server.py             # MCP 入口：parse_paper / decompose / render_svg / render_emf
    llm/provider.py       # 国内模型抽象（Qwen/GLM/DeepSeek, OpenAI 兼容）
    tools/parse.py        # 论文解析（MinerU / pdfplumber）
    tools/decompose.py    # LLM 拆解 → figure_spec
    tools/render.py       # SVG / EMF 渲染
examples/              # 示例
loot/                  # 输出目录（SVG/EMF/解析结果）
```

## 快速开始

### 1. 安装 MCP server

```bash
cd mcp
pip install -e .
# 需解析：pip install pdfplumber  →或→  pip install mineru
# 需 EMF 转换：pip install cairosvg pillow
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

### 3. 在 opencode 使用

skill 位于 `skill/`，MCP server 在 `mcp/`。详见 `mcp/README.md`。

## 路线图

- [x] 工作流定义 + skill 骨架 + MCP server 骨架
- [ ] MinerU 高精度解析接入
- [ ] figure_spec 渲染器完善（分组布局/图标匹配）
- [ ] 机制图图标素材库集成（research-figure-library / Bioicons / Servier）
- [ ] draw.io 实时画布 MCP（二期）

## License

MIT
