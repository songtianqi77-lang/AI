"""
飞书消息格式化与 Webhook 推送模块
使用飞书富文本消息（post 类型）格式，兼容性最佳。
消息结构：
  - 标题卡片（含日期）
  - 英文资讯区块（6条，中英对照）
  - 中文资讯区块（4条）
  - 底部说明
"""

import json
import logging
import os
from datetime import datetime, timezone, timedelta

import requests

logger = logging.getLogger(__name__)

# 北京时区
CST = timezone(timedelta(hours=8))

CATEGORY_EMOJI = {
    "技术突破": "🔬",
    "产品发布": "🚀",
    "行业动态": "📊",
    "学术研究": "📄",
}


def get_category_emoji(category: str) -> str:
    for key, emoji in CATEGORY_EMOJI.items():
        if key in category:
            return emoji
    return "📌"


def build_feishu_card(selected: dict) -> dict:
    """
    构建飞书 Interactive Card (schema 2.0) 消息体。
    """
    now_cst = datetime.now(tz=CST)
    date_str = now_cst.strftime("%Y年%m月%d日")
    weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_str = weekday_map[now_cst.weekday()]

    en_articles = selected.get("en_articles", [])
    zh_articles = selected.get("zh_articles", [])

    elements = []

    # ── 英文资讯区块 ──────────────────────────────────────
    elements.append({
        "tag": "markdown",
        "content": "**🌐 英文资讯 | English News**（中英对照）",
        "text_align": "left",
    })
    elements.append({"tag": "hr"})

    for i, item in enumerate(en_articles, 1):
        category = item.get("category", "行业动态")
        emoji = get_category_emoji(category)
        source = item.get("source", "")
        title_en = item.get("title_en", "")
        title_zh = item.get("title_zh", "")
        summary_zh = item.get("summary_zh", "")
        summary_en = item.get("summary_en", "")
        link = item.get("link", "")

        content_lines = [
            f"**{i}. {emoji} {title_zh}**",
            f"> {title_en}",
            f"",
            f"**【中文摘要】** {summary_zh}",
            f"",
            f"**【English Summary】** {summary_en}",
            f"",
            f"📎 来源：{source}　[阅读原文]({link})",
        ]
        elements.append({
            "tag": "markdown",
            "content": "\n".join(content_lines),
        })
        if i < len(en_articles):
            elements.append({"tag": "hr"})

    # ── 中文资讯区块 ──────────────────────────────────────
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "markdown",
        "content": "**🇨🇳 中文资讯 | Chinese News**",
        "text_align": "left",
    })
    elements.append({"tag": "hr"})

    for i, item in enumerate(zh_articles, 1):
        category = item.get("category", "行业动态")
        emoji = get_category_emoji(category)
        source = item.get("source", "")
        title = item.get("title", "")
        summary_zh = item.get("summary_zh", "")
        link = item.get("link", "")

        content_lines = [
            f"**{i}. {emoji} {title}**",
            f"",
            f"**【摘要】** {summary_zh}",
            f"",
            f"📎 来源：{source}　[阅读原文]({link})",
        ]
        elements.append({
            "tag": "markdown",
            "content": "\n".join(content_lines),
        })
        if i < len(zh_articles):
            elements.append({"tag": "hr"})

    # ── 底部说明 ──────────────────────────────────────────
    elements.append({"tag": "hr"})
    elements.append({
        "tag": "markdown",
        "content": (
            f"_由 AI 资讯机器人自动生成 · {date_str} {weekday_str} 07:00 北京时间_\n"
            "_渠道：Hacker News · Reddit · ArXiv · OpenAI Blog · HuggingFace · 36氪 · 机器之心 · 雷锋网 · 少数派_"
        ),
        "text_align": "center",
    })

    card = {
        "msg_type": "interactive",
        "card": {
            "schema": "2.0",
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🤖 每日 AI 资讯早报 · {date_str} {weekday_str}",
                },
                "subtitle": {
                    "tag": "plain_text",
                    "content": f"精选 {len(en_articles)} 条英文 + {len(zh_articles)} 条中文 AI 热点资讯",
                },
                "template": "blue",
            },
            "body": {
                "direction": "vertical",
                "padding": "12px 12px 12px 12px",
                "elements": elements,
            },
        },
    }
    return card


def build_feishu_post(selected: dict) -> dict:
    """
    构建飞书富文本消息（post 类型）作为备用格式。
    当 interactive card 不可用时使用。
    """
    now_cst = datetime.now(tz=CST)
    date_str = now_cst.strftime("%Y年%m月%d日")
    weekday_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    weekday_str = weekday_map[now_cst.weekday()]

    en_articles = selected.get("en_articles", [])
    zh_articles = selected.get("zh_articles", [])

    content_blocks = []

    # 英文资讯
    content_blocks.append([{"tag": "text", "text": "🌐 英文资讯（中英对照）\n", "style": ["bold"]}])

    for i, item in enumerate(en_articles, 1):
        category = item.get("category", "行业动态")
        emoji = get_category_emoji(category)
        source = item.get("source", "")
        title_en = item.get("title_en", "")
        title_zh = item.get("title_zh", "")
        summary_zh = item.get("summary_zh", "")
        summary_en = item.get("summary_en", "")
        link = item.get("link", "")

        block = [
            {"tag": "text", "text": f"{i}. {emoji} {title_zh}\n", "style": ["bold"]},
            {"tag": "text", "text": f"   {title_en}\n"},
            {"tag": "text", "text": f"   【中文摘要】{summary_zh}\n"},
            {"tag": "text", "text": f"   【English】{summary_en}\n"},
            {"tag": "text", "text": f"   来源：{source}  "},
            {"tag": "a", "text": "阅读原文", "href": link},
            {"tag": "text", "text": "\n\n"},
        ]
        content_blocks.append(block)

    # 中文资讯
    content_blocks.append([{"tag": "text", "text": "🇨🇳 中文资讯\n", "style": ["bold"]}])

    for i, item in enumerate(zh_articles, 1):
        category = item.get("category", "行业动态")
        emoji = get_category_emoji(category)
        source = item.get("source", "")
        title = item.get("title", "")
        summary_zh = item.get("summary_zh", "")
        link = item.get("link", "")

        block = [
            {"tag": "text", "text": f"{i}. {emoji} {title}\n", "style": ["bold"]},
            {"tag": "text", "text": f"   【摘要】{summary_zh}\n"},
            {"tag": "text", "text": f"   来源：{source}  "},
            {"tag": "a", "text": "阅读原文", "href": link},
            {"tag": "text", "text": "\n\n"},
        ]
        content_blocks.append(block)

    # 底部
    content_blocks.append([{
        "tag": "text",
        "text": f"由 AI 资讯机器人自动生成 · {date_str} {weekday_str} 07:00 北京时间",
    }])

    return {
        "msg_type": "post",
        "content": {
            "post": {
                "zh_cn": {
                    "title": f"🤖 每日 AI 资讯早报 · {date_str} {weekday_str}",
                    "content": content_blocks,
                }
            }
        }
    }


def send_to_feishu(webhook_url: str, payload: dict) -> bool:
    """发送消息到飞书 Webhook。"""
    if not webhook_url:
        logger.error("FEISHU_WEBHOOK_URL is not set!")
        return False

    try:
        resp = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") == 0 or result.get("StatusCode") == 0:
            logger.info("Message sent to Feishu successfully!")
            return True
        else:
            logger.error(f"Feishu API error: {result}")
            return False
    except Exception as e:
        logger.error(f"Failed to send to Feishu: {e}")
        return False


def notify(selected: dict, webhook_url: str = None) -> bool:
    """
    主推送函数：构建消息并发送到飞书。
    优先使用 Interactive Card，失败时降级为富文本。
    """
    if webhook_url is None:
        webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")

    if not webhook_url:
        logger.error("No Feishu webhook URL provided!")
        return False

    # 尝试 Interactive Card
    card_payload = build_feishu_card(selected)
    success = send_to_feishu(webhook_url, card_payload)

    if not success:
        logger.warning("Card message failed, trying rich text (post) format...")
        post_payload = build_feishu_post(selected)
        success = send_to_feishu(webhook_url, post_payload)

    return success


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # 测试用假数据
    test_data = {
        "en_articles": [
            {
                "index": 1,
                "title_en": "OpenAI releases GPT-5 with unprecedented reasoning capabilities",
                "title_zh": "OpenAI 发布 GPT-5，推理能力达到新高度",
                "summary_zh": "OpenAI 正式发布 GPT-5 模型，该模型在数学推理、代码生成和多步骤任务规划方面取得重大突破，在多项基准测试中超越人类专家水平。",
                "summary_en": "OpenAI officially released GPT-5, achieving major breakthroughs in mathematical reasoning, code generation, and multi-step task planning.",
                "source": "OpenAI Blog",
                "link": "https://openai.com/blog",
                "category": "产品发布",
            },
            {
                "index": 2,
                "title_en": "Google DeepMind's AlphaFold 3 predicts protein-drug interactions",
                "title_zh": "谷歌 DeepMind AlphaFold 3 可预测蛋白质-药物相互作用",
                "summary_zh": "AlphaFold 3 将预测能力从蛋白质结构扩展到蛋白质与 DNA、RNA 和小分子药物的相互作用，为药物发现带来革命性变化。",
                "summary_en": "AlphaFold 3 extends prediction capabilities to protein-DNA, RNA, and small molecule drug interactions, revolutionizing drug discovery.",
                "source": "Hacker News",
                "link": "https://news.ycombinator.com",
                "category": "技术突破",
            },
        ],
        "zh_articles": [
            {
                "index": 1,
                "title": "百度文心一言 4.0 发布，多模态能力大幅提升",
                "summary_zh": "百度正式发布文心一言 4.0 版本，在图像理解、视频生成和长文本处理方面均有显著提升，并推出企业级 API 服务。",
                "source": "36氪",
                "link": "https://36kr.com",
                "category": "产品发布",
            },
            {
                "index": 2,
                "title": "清华大学发布开源大模型 ChatGLM4，性能媲美 GPT-4",
                "summary_zh": "清华大学 KEG 实验室发布 ChatGLM4 开源版本，在中文理解、代码生成和数学推理方面表现优异，支持 128K 上下文窗口。",
                "source": "机器之心",
                "link": "https://www.jiqizhixin.com",
                "category": "技术突破",
            },
        ],
    }

    # 打印消息结构（不实际发送）
    card = build_feishu_card(test_data)
    print("=== Feishu Card Payload ===")
    print(json.dumps(card, ensure_ascii=False, indent=2)[:2000])
    print("\n... (truncated)")

    webhook = os.environ.get("FEISHU_WEBHOOK_URL", "")
    if webhook:
        print("\n=== Sending to Feishu ===")
        result = notify(test_data, webhook)
        print(f"Result: {'Success' if result else 'Failed'}")
    else:
        print("\n[INFO] FEISHU_WEBHOOK_URL not set, skipping actual send.")
