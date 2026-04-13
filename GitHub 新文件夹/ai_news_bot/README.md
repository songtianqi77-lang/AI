# 🤖 每日 AI 资讯聚合推送机器人 (Feishu Bot)

本项目是一个全自动的 AI 资讯聚合与推送系统。每天自动从各大知名英文与中文资讯源抓取最新 AI 资讯，通过大语言模型（LLM）提取摘要、翻译英文内容，并精选 Top 10 热点（6 条英文，4 条中文），在北京时间早上 7 点自动推送到飞书群。

## 🌟 核心特性

- **多渠道聚合**：
  - **英文源 (60%)**：Hacker News, Reddit (r/MachineLearning, r/artificial, r/LocalLLaMA), ArXiv, OpenAI Blog, Hugging Face Blog。
  - **中文源 (40%)**：36氪 AI, 机器之心, 雷锋网, 开源中国, InfoQ, 少数派。
- **智能摘要与翻译**：利用 OpenAI 兼容的 LLM 自动提取核心信息，英文资讯自动生成中英对照。
- **智能排序**：基于来源权重（社媒 > 聚合社区 > 官方博客 > 学术前沿）和社区热度进行打分筛选。
- **精美飞书卡片**：采用飞书 Interactive Card (schema 2.0) 富文本卡片格式，排版清晰美观。
- **零成本自动化**：基于 GitHub Actions 的 `schedule` 触发器定时运行，无需自建服务器。

## 🚀 快速部署指南

只需 3 步即可在你的 GitHub 账号下免费部署此服务。

### 1. Fork 本仓库
点击右上角的 **Fork** 按钮，将本仓库复制到你的个人 GitHub 账号下。

### 2. 获取飞书 Webhook 地址
1. 在飞书客户端中，进入你想要推送资讯的群聊。
2. 点击右上角「设置」 -> 「群机器人」 -> 「添加机器人」。
3. 选择「自定义机器人」，设置头像和名称。
4. 复制生成的 **Webhook 地址**（例如 `https://open.feishu.cn/open-apis/bot/v2/hook/xxx...`）。
5. （强烈建议）在机器人的安全设置中，设置自定义关键词为 `AI` 或 `资讯`。

### 3. 配置 GitHub Secrets
1. 进入你 Fork 后的仓库，点击顶部菜单栏的 **Settings**。
2. 在左侧边栏找到 **Secrets and variables** -> **Actions**。
3. 点击 **New repository secret**，添加以下两个 Secret：
   - `FEISHU_WEBHOOK_URL`：填入你刚才复制的飞书机器人 Webhook 地址。
   - `OPENAI_API_KEY`：填入你的 OpenAI API Key（或其他兼容模型的 Key，如 DeepSeek、通义千问等）。
4. （可选）如果你使用的是非 OpenAI 官方 API，可以在 **Variables** 中添加 `OPENAI_BASE_URL` 和 `LLM_MODEL` 变量来指定代理地址和模型名称。

### 4. 启用 GitHub Actions
1. 点击仓库顶部菜单栏的 **Actions**。
2. 如果看到提示 "I understand my workflows, go ahead and enable them"，点击确认。
3. 在左侧边栏选择 **Daily AI News Push** 工作流。
4. 点击右侧的 **Run workflow** 手动触发一次，测试是否能成功推送到飞书群。

---

## 🕒 定时执行时间说明
默认的执行时间在 `.github/workflows/daily_push.yml` 中配置：
```yaml
schedule:
  - cron: "0 23 * * *"
```
由于 GitHub Actions 使用 UTC 时间，`23:00 UTC` 对应北京时间（UTC+8）的 **早上 07:00**。

---

## 🛠️ 本地开发与测试

如果你想在本地修改代码或测试运行：

1. 克隆代码并安装依赖：
   ```bash
   git clone <your-repo-url>
   cd ai_news_bot
   pip install -r requirements.txt
   ```
2. 设置环境变量：
   ```bash
   export FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/..."
   export OPENAI_API_KEY="sk-..."
   ```
3. 运行主程序：
   ```bash
   python main.py
   ```

## 📄 许可证
MIT License
