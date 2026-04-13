# AI 资讯聚合推送系统架构设计

## 系统概述
本系统旨在每天自动抓取多个中英文 AI 资讯渠道的最新信息，利用大语言模型（LLM）提取热点并生成摘要，最后将精选后的 Top 10 资讯（中英比例 4:6，英文包含中英对照）通过 Webhook 定时推送到飞书群。系统基于 GitHub Actions 实现自动化定时运行，无需额外服务器成本。

## 核心模块

### 1. 资讯抓取模块 (Scraper Module)
负责从各个数据源获取最新资讯。
- **英文渠道 (60%)**：Hacker News (API/RSS), Reddit r/MachineLearning & r/artificial (RSS), ArXiv (RSS)
- **中文渠道 (40%)**：知乎 AI 话题 (RSS/网页抓取), 36氪 AI 频道 (RSS/网页抓取), 机器之心等微信公众号聚合源 (RSS)
- **数据结构**：统一化为 `Article(title, link, source, publish_time, summary/content)`

### 2. 热点提取与排序模块 (Processor Module)
负责对抓取到的海量资讯进行过滤、评分和摘要生成。
- **去重与过滤**：去除重复新闻和非 AI 相关内容。
- **优先级排序**：根据来源权重（社媒 > 聚合社区 > 官方博客 > 学术前沿）和时效性进行初步打分。
- **LLM 处理**：调用 OpenAI 兼容 API（如 GPT-4o-mini 或 Gemini-2.5-flash）对高分资讯进行处理：
  - 提取核心摘要。
  - 对于英文资讯，生成中文翻译，保留英文原文（中英对照）。
  - 最终选出 10 条（6 条英文，4 条中文）。

### 3. 消息格式化与推送模块 (Notifier Module)
负责将处理好的数据组装成飞书消息卡片（Message Card）并发送。
- **消息格式**：使用飞书富文本消息（`msg_type: "interactive"`）的 Card 结构。
- **排版设计**：包含标题（如“🤖 每日 AI 资讯早报”）、分割线、以及 10 条资讯的列表（每条包含标题、摘要、来源标签和原文链接）。

### 4. 自动化调度模块 (Automation Module)
- **平台**：GitHub Actions
- **触发器**：`schedule` (cron 表达式 `0 23 * * *`，即 UTC 23:00，对应北京时间早上 7:00)
- **环境变量/Secrets**：配置 `FEISHU_WEBHOOK_URL` 和 `LLM_API_KEY`。

## 数据流向
1. GitHub Actions 定时触发 Python 脚本。
2. 脚本并行调用各个数据源的 API 或解析 RSS 订阅。
3. 汇总数据，清洗后发送给 LLM API。
4. LLM 返回结构化（JSON）的精选结果。
5. 脚本将 JSON 结果渲染为飞书 Message Card JSON。
6. 通过 HTTP POST 请求发送至飞书 Webhook。
7. 运行结束，记录日志。
