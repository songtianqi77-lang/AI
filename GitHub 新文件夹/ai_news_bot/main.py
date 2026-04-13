"""
AI 资讯聚合推送系统 - 主入口
每天北京时间 07:00 由 GitHub Actions 触发执行。
"""

import logging
import os
import sys
import json
from datetime import datetime, timezone, timedelta

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

CST = timezone(timedelta(hours=8))


def main():
    logger.info("=" * 60)
    logger.info("AI 资讯聚合推送系统启动")
    logger.info(f"当前时间（北京）: {datetime.now(tz=CST).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 检查必要环境变量
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if not webhook_url:
        logger.error("环境变量 FEISHU_WEBHOOK_URL 未设置！")
        sys.exit(1)

    openai_api_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_api_key:
        logger.warning("环境变量 OPENAI_API_KEY 未设置，将使用降级模式（无 LLM 摘要）")

    # Step 1: 抓取资讯
    logger.info("\n[Step 1/3] 开始抓取各渠道资讯...")
    try:
        from scraper import fetch_all_articles
        raw_articles = fetch_all_articles()
        en_count = len(raw_articles.get("en", []))
        zh_count = len(raw_articles.get("zh", []))
        logger.info(f"抓取完成：英文 {en_count} 条，中文 {zh_count} 条")
    except Exception as e:
        logger.error(f"资讯抓取失败: {e}", exc_info=True)
        sys.exit(1)

    if en_count == 0 and zh_count == 0:
        logger.error("未抓取到任何资讯，退出")
        sys.exit(1)

    # Step 2: 处理与精选
    logger.info("\n[Step 2/3] 开始热点提取与摘要生成...")
    try:
        from processor import process_articles
        selected = process_articles(raw_articles)
        en_selected = len(selected.get("en_articles", []))
        zh_selected = len(selected.get("zh_articles", []))
        logger.info(f"精选完成：英文 {en_selected} 条，中文 {zh_selected} 条")
    except Exception as e:
        logger.error(f"资讯处理失败: {e}", exc_info=True)
        sys.exit(1)

    # 保存结果到文件（用于调试）
    try:
        output_path = f"/tmp/ai_news_{datetime.now(tz=CST).strftime('%Y%m%d')}.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(selected, f, ensure_ascii=False, indent=2)
        logger.info(f"精选结果已保存至 {output_path}")
    except Exception as e:
        logger.warning(f"保存结果文件失败: {e}")

    # Step 3: 推送到飞书
    logger.info("\n[Step 3/3] 开始推送到飞书群...")
    try:
        from notifier import notify
        success = notify(selected, webhook_url)
        if success:
            logger.info("✅ 推送成功！")
        else:
            logger.error("❌ 推送失败！")
            sys.exit(1)
    except Exception as e:
        logger.error(f"推送失败: {e}", exc_info=True)
        sys.exit(1)

    logger.info("\n" + "=" * 60)
    logger.info("AI 资讯聚合推送系统运行完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
