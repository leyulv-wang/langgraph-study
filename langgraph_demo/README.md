# LangGraph Demo：多智能体 AI 情报系统

该项目在 LangGraph 标准项目结构下实现一个可运行的多智能体系统，用于：

- 检索 GitHub 指定时间窗口内 AI 相关热门项目（按增长/热度）
- 聚合多来源 AI 新闻（RSS/Atom），去重、关键词提取、摘要
- 多智能体编排：协调智能体 + 项目分析智能体 + 新闻分类智能体 + 报告聚合智能体
- 输出结构化报告：JSON 与 Markdown

配置文件：`config/settings.json`

详细技术文档与从零到一教程：

- [TECHNICAL_GUIDE.md](file:///d:/python/sample/sample/langgraph_demo/docs/TECHNICAL_GUIDE.md)

## 依赖与环境变量

### 必需

- Python 3.11+（`langgraph dev` 本地开发模式要求）
- `langgraph-cli[inmem]`（运行本地 API）

### 可选

- `GITHUB_TOKEN`：用于提升 GitHub API 配额并支持更准确的“窗口内 star 增量”统计（GraphQL）

`.env` 示例（你可以已有）：

```text
GITHUB_TOKEN=...
```

## 运行（LangGraph API + Studio）

```bash
pip install -e . "langgraph-cli[inmem]"
langgraph dev
```

启动后可打开：

- `http://127.0.0.1:2024/docs`
- `https://smith.langchain.com/studio/?baseUrl=http://127.0.0.1:2024`

## 运行（命令行）

```bash
python -m agent.cli --days 14 --format markdown
python -m agent.cli --days 14 --format both --out-dir ./outputs
```

参数：

- `--github-topic` 可重复指定，例如 `--github-topic ai --github-topic llm`
- `--github-language` 可重复指定，例如 `--github-language Python --github-language TypeScript`
- `--github-limit` 控制返回项目数量

## 说明

- GitHub “指定时间段内 star 增量”统计需要 `GITHUB_TOKEN` 才能稳定实现；无 token 时会回退为按 `stars` 排序的近似热度。
- 新闻源基于 RSS/Atom；可在 `config/settings.json` 扩展更多来源。
