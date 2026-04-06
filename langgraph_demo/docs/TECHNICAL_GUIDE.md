# LangGraph Demo：多智能体 AI 情报系统（完整技术文档与教程）

本项目基于 LangGraph 的标准项目结构，实现一个“多智能体编排 + 工具链”的演示系统，用于：

- GitHub 热门 AI 项目检索（时间窗口内的“热度/增长”近似）
- AI 新闻聚合（RSS/Atom：TechCrunch AI、arXiv cs.AI/cs.LG）
- 多智能体编排（协调器 + 项目分析 + 新闻分类 + 报告聚合）
- 输出结构化报告（JSON / Markdown）

你可以用两种方式使用：

- 本地命令行一次性生成报告（推荐初学者）
- 通过 LangGraph API/Studio 运行并可视化调试

---

## 1. 项目架构说明

### 1.1 总览（数据流）

输入（运行参数） → GitHub 检索 → 项目质量评估 → 新闻抓取 → 新闻分类 → 结果关联与报告输出

### 1.2 LangGraph 工作流（StateGraph）

核心工作流定义在 [graph.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/graph.py)：

- State：`AppState`（见 [state.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/state.py)）
- 节点（Nodes）：
  - `coordinator`：协调智能体，决定下一步执行哪个节点
  - `github_fetch`：GitHub 热门项目检索
  - `project_analyze`：项目质量评估（启发式打分）
  - `news_fetch`：RSS/Atom 新闻抓取与清洗
  - `news_classify`：按领域分类（关键词规则）
  - `report`：报告聚合（JSON + Markdown）
- 边（Edges）：
  - `START -> coordinator`
  - 每个业务节点执行后回到 `coordinator`
  - `coordinator` 通过条件边选择下一跳（直到 `END`）

这种结构的好处：

- 每个节点都像一个“子智能体/子模块”，逻辑高度可替换
- 运行时可在 Studio 可视化看到每一步的输入输出，方便教学与调试

### 1.3 “多智能体”在这里是什么意思

这里的“多智能体”是指“多角色节点”：

- 协调智能体：负责调度与阶段推进（类似项目经理）
- 项目分析智能体：负责评估仓库质量指标（类似代码审查者）
- 新闻分类智能体：负责将新闻按领域分类（类似编辑）
- 报告聚合智能体：负责把信息关联并生成报告（类似分析师）

这是一种非常适合初学者的多智能体落地方式：先用确定性规则实现闭环，再逐步引入 LLM 推理增强（可选扩展）。

---

## 2. 目录结构（标准 LangGraph 项目）

项目根目录：[langgraph_demo](file:///d:/python/sample/sample/langgraph_demo)

关键目录：

- `src/agent/graph.py`：LangGraph 主图入口（langgraph.json 指向它）
- `src/agent/state.py`：全局状态结构（AppState/RunParams）
- `src/agent/agents/`：各“智能体节点”实现
  - `coordinator.py`：协调器
  - `github_fetch.py`：GitHub 检索节点
  - `project_analyzer.py`：项目分析节点
  - `news_fetch.py`：新闻抓取节点
  - `news_classifier.py`：新闻分类节点
  - `report_aggregator.py`：报告聚合节点
- `src/agent/tools/`：工具层（负责“外部世界 IO”）
  - `github_tools.py`：GitHub API 客户端 + 清洗
  - `news_tools.py`：RSS/Atom 抓取 + 去重/摘要/关键词
- `src/agent/utils/`：基础能力（重试、限流、文本处理、日志）
  - `http_client.py`：HTTP 请求 + 重试
  - `rate_limit.py`：简单速率限制
  - `text.py`：关键词提取、摘要
  - `logging.py`：日志配置
- `config/settings.json`：数据源与限流配置
- `langgraph.json`：LangGraph Server 入口配置
- `tests/`：pytest 测试（unit + integration）

---

## 3. 环境配置要求

### 3.1 Python 版本

- Python 3.11+（你当前是 3.11.7，满足）

### 3.2 Conda 与环境位置

你系统里可能出现：

- conda base 在 C 盘（例如 `C:\\Users\\Administrator\\anaconda3`）
- 某些 env 在 D 盘（例如 `D:\\anaconda3\\envs\\langgraph`）

这是正常的。关键是：运行命令时必须使用正确环境的 `python.exe`。

---

## 4. 依赖安装步骤（从零开始）

下面给两种方式：你可以选其中一种坚持到底。

### 方式 A：始终显式使用项目环境的 python.exe（最稳）

以你的环境为例（env 名：`langgraph`）：

1) 安装/升级项目依赖（本项目最小依赖）：

```powershell
D:\anaconda3\envs\langgraph\python.exe -m pip install -U pip
D:\anaconda3\envs\langgraph\python.exe -m pip install -U langgraph python-dotenv pytest anyio
```

2) 安装 LangGraph CLI（用于 `langgraph dev`）：

```powershell
D:\anaconda3\envs\langgraph\python.exe -m pip install -U "langgraph-cli[inmem]"
```

3) 可选：把当前项目安装成可导入包（建议做，避免 import 问题）：

```powershell
D:\anaconda3\envs\langgraph\python.exe -m pip install -e .
```

验证：

```powershell
D:\anaconda3\envs\langgraph\python.exe -c "import langgraph; import agent; print('ok')"
```

### 方式 B：激活环境后用 python/pip（更方便但更容易装错）

```powershell
conda activate langgraph
python -m pip install -U "langgraph-cli[inmem]" -e .
python -m pytest -q
```

如果你遇到“终端显示激活了，但 python 仍然指向 base”，优先改用方式 A。

---

## 5. 配置文件说明

### 5.1 `langgraph.json`

文件：[langgraph.json](file:///d:/python/sample/sample/langgraph_demo/langgraph.json)

关键字段：

- `graphs.agent`：指向 graph 入口 `./src/agent/graph.py:graph`
- `env`：指定 `.env` 文件路径

### 5.2 `config/settings.json`

文件：[settings.json](file:///d:/python/sample/sample/langgraph_demo/config/settings.json)

你可以配置：

- GitHub 搜索默认 topic、language、limit、超时、分页
- 新闻源列表（RSS/Atom URL）
- 速率限制：每分钟最大请求数（GitHub/News）

### 5.3 `.env`

可选环境变量（建议放在 `.env`）：

- `GITHUB_TOKEN`：强烈建议配置
  - 有 token 才能更稳定地访问 GitHub API
  - 若要统计“时间窗口内 star 增量”，需要 GraphQL 调用；无 token 时会回退到近似排序

注意：如果 `.env` 包含中文或 emoji，可能在某些 Windows 控制台编码下触发解码问题。建议尽量使用 ASCII，或确保终端使用 UTF-8。

---

## 6. 核心功能模块实现细节

### 6.1 GitHub 热门 AI 项目检索模块

入口：

- 节点：`github_fetch` [github_fetch.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/agents/github_fetch.py)
- 工具：`get_hot_ai_repos` [github_tools.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/tools/github_tools.py)

实现思路：

1) 先用 REST Search API 搜索候选仓库（按 stars 排序，限定 pushed>=since + topic/language）
2) 若提供 `GITHUB_TOKEN`，再用 GraphQL 拉取 stargazers 的 starredAt，计算 since 时间之后的 star 数（近似“增长”）
3) 对输出做清洗与统一字段格式（full_name/url/language/stars/forks/issues/archived/star_growth…）

速率限制与重试：

- `agent.utils.rate_limit.RateLimiter`：每分钟最多 N 次请求
- `agent.utils.http_client.request`：对 429/5xx 做指数退避重试

### 6.2 AI 新闻聚合模块

入口：

- 节点：`news_fetch` [news_fetch.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/agents/news_fetch.py)
- 工具：`fetch_ai_news` [news_tools.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/tools/news_tools.py)

实现：

- RSS：解析 `<channel><item>`
- Atom（arXiv）：解析 Atom namespace 的 `<entry>`
- 去重：按 URL/Title 去重
- 关键词：`extract_keywords`（简易词频+停用词）
- 摘要：`simple_summary`（按句号切前 N 句）

### 6.3 智能体编排系统（协调/分析/分类/聚合）

- 协调：`coordinator` 决定 next_node（状态机推进）[coordinator.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/agents/coordinator.py)
- 项目分析：启发式得分（stars/forks/issues/star_growth/archived）[project_analyzer.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/agents/project_analyzer.py)
- 新闻分类：关键词匹配分类（Agent/LLM/RAG/Multimodal/Robotics/Research/Industry/Policy…）[news_classifier.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/agents/news_classifier.py)
- 报告聚合：生成 report_json + report_markdown，并做“项目-新闻”关键词重叠关联 [report_aggregator.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/agents/report_aggregator.py)

### 6.4 结果整合与展示

- CLI：`python -m agent.cli ...` [cli.py](file:///d:/python/sample/sample/langgraph_demo/src/agent/cli.py)
- 输出格式：
  - Markdown：便于阅读
  - JSON：便于下游系统接入

---

## 7. 运行教程：从项目初始化到最终运行（逐步演示）

### 阶段 0：确认你在正确的环境

推荐用“明确解释器路径”的方式验证：

```powershell
D:\anaconda3\envs\langgraph\python.exe -c "import sys; print(sys.executable)"
```

期望输出：

`D:\anaconda3\envs\langgraph\python.exe`

### 阶段 1：安装依赖

```powershell
D:\anaconda3\envs\langgraph\python.exe -m pip install -U "langgraph-cli[inmem]" -e .
```

验证：

```powershell
D:\anaconda3\envs\langgraph\python.exe -m pytest -q
```

预期：全部测试通过。

### 阶段 2：命令行生成报告（推荐初学者第一步）

```powershell
D:\anaconda3\envs\langgraph\python.exe -m agent.cli --days 7 --format markdown
```

验证点：

- 终端输出包含 `# AI Weekly Brief`
- `AI 新闻（按分类）` 有内容
- 如果 GitHub 列表为空：多半是 GitHub 访问受限或 token 缺失（见下一节）

### 阶段 3：可选增强（推荐）：配置 GitHub Token

在 `.env` 中添加：

```text
GITHUB_TOKEN=你的token
```

再次运行：

```powershell
D:\anaconda3\envs\langgraph\python.exe -m agent.cli --days 14 --format both --out-dir ./outputs
```

验证点：

- `outputs/report.md` 存在
- `outputs/report.json` 存在
- GitHub 表格开始出现项目

### 阶段 4：启动 LangGraph Server + Studio（可视化调试）

```powershell
D:\anaconda3\envs\langgraph\Scripts\langgraph.exe dev
```

打开：

- API Docs：`http://127.0.0.1:2024/docs`
- Studio：`https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

在 Studio 中：

- 选择 graph：`agent`
- 输入初始 state：

```json
{
  "phase": "start",
  "params": {
    "days": 14,
    "github_limit": 20,
    "output_format": "markdown"
  }
}
```

验证点：

- 你能看到节点按顺序执行：coordinator → github_fetch → … → report
- 每个节点的输出字段会进入 state（例如 `news_items`、`report_markdown`）

---

## 8. 编译/构建流程

该项目本质是 Python 包 + LangGraph Server 的图定义：

- 本地开发：`langgraph dev`
- 交付：通常打包成 Docker（`langgraph build`）或用 LangGraph 平台方案

如果你只做学习/演示：无需额外 build，直接跑 CLI 或 dev server 即可。

---

## 9. 部署上线方案（演示级）

最简单的上线方式（演示/内网）：

- 用 `langgraph dev` 仅适合本地开发，不建议生产
- 生产更建议：
  - `langgraph build` 构建镜像
  - `langgraph up` 本地/服务器起 docker（需要 docker 环境）

注意：不同版本的 LangGraph Platform 对生产部署可能有额外要求（例如 license / LangSmith）。如果你要部署到公网/生产，请先确认你使用的 LangGraph 版本与授权方式。

---

## 10. 开发调试指南（初学者建议）

### 10.1 最推荐的调试顺序

1) CLI 跑通（最直观，最快看到结果）
2) pytest 全绿（保证节点逻辑可回归）
3) Studio 可视化调试（看 state 在每一步如何变化）

### 10.2 常见问题与解决

- 终端里 `python` 指向 base（C 盘），导致装错包  
  - 解决：用 `D:\anaconda3\envs\langgraph\python.exe -m pip ...`
- GitHub 项目列表为空  
  - 可能原因：GitHub API 限流/无 token；网络访问受限；topic/language 过滤过严  
  - 解决：配置 `GITHUB_TOKEN`；减小过滤条件；降低 `days` 或增加 `limit`
- RSS/Atom 抓取为空  
  - 可能原因：网络限制；源地址变更  
  - 解决：替换 `config/settings.json` 中 sources；先用浏览器打开 RSS/Atom URL 验证可访问

---

## 11. 下一步学习路线（建议）

当你把这套规则引擎跑通后，建议按以下顺序升级为“真正的 LLM 多智能体系统”：

1) 在 `news_fetch` 后增加一个“LLM 摘要/关键词提取”节点（可替换 `simple_summary/extract_keywords`）
2) 在 `news_classify` 中用 LLM 做更准确的分类（输出 JSON schema）
3) 在 `report_aggregator` 中用 LLM 生成更像“分析报告”的段落，并保留 JSON 结构化结果

