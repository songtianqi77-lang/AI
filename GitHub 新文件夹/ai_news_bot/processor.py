"""
热点提取与排序模块
功能：
  1. 对抓取到的文章进行去重、过滤和初步评分
  2. 按优先级（社媒>聚合社区>官方博客>学术前沿）和热度排序
  3. 调用 LLM API 生成摘要，英文文章生成中英对照内容
  4. 最终输出 10 条精选资讯（6 条英文 + 4 条中文）
"""

import json
import logging
import os
import re
import time
from typing import Optional

from openai import OpenAI

from scraper import Article

logger = logging.getLogger(__name__)

# LLM 配置
LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4.1-mini")
LLM_MAX_TOKENS = 4000

# 目标比例
TARGET_EN = 6
TARGET_ZH = 4
TARGET_TOTAL = TARGET_EN + TARGET_ZH

# 优先级权重（数值越小优先级越高）
PRIORITY_WEIGHT = {1: 4, 2: 3, 3: 2, 4: 1}

# 来源可信度加权（部分高质量来源额外加分）
SOURCE_BONUS = {
    "Hacker News": 2,
    "Reddit r/MachineLearning": 3,
    "Reddit r/LocalLLaMA": 2,
    "OpenAI Blog": 3,
    "Hugging Face Blog": 2,
    "机器之心": 3,
    "36氪": 2,
}


def _get_llm_client() -> OpenAI:
    """获取 OpenAI 兼容客户端。"""
    return OpenAI()  # 使用环境变量中预配置的 API key 和 base_url


def deduplicate(articles: list[Article]) -> list[Article]:
    """基于标题相似度去重。"""
    seen_titles = set()
    unique = []
    for a in articles:
        # 简单规范化：小写、去标点
        normalized = re.sub(r"[^\w\s]", "", a.title.lower()).strip()
        # 取前 30 个字符作为指纹
        fingerprint = normalized[:30]
        if fingerprint not in seen_titles:
            seen_titles.add(fingerprint)
            unique.append(a)
    return unique


def compute_base_score(article: Article) -> float:
    """计算文章的基础评分（用于初步排序）。"""
    score = 0.0
    # 优先级权重
    score += PRIORITY_WEIGHT.get(article.priority, 1) * 10
    # 来源加分
    score += SOURCE_BONUS.get(article.source, 0) * 5
    # 热度加分（HN score, Reddit upvotes 等）
    if article.score > 0:
        score += min(article.score / 10, 20)  # 最多加 20 分
    return score


def pre_rank(articles: list[Article], top_n: int = 30) -> list[Article]:
    """初步排序，取 top_n 候选文章。"""
    for a in articles:
        a.score = compute_base_score(a)
    articles.sort(key=lambda x: x.score, reverse=True)
    return articles[:top_n]


def build_llm_prompt(en_candidates: list[Article], zh_candidates: list[Article]) -> str:
    """构建发送给 LLM 的 prompt。"""
    en_list = "\n".join(
        f"{i+1}. [{a.source}] {a.title}\n   摘要原文: {a.summary[:200] if a.summary else '(无摘要)'}\n   链接: {a.link}"
        for i, a in enumerate(en_candidates)
    )
    zh_list = "\n".join(
        f"{i+1}. [{a.source}] {a.title}\n   摘要: {a.summary[:200] if a.summary else '(无摘要)'}\n   链接: {a.link}"
        for i, a in enumerate(zh_candidates)
    )

    prompt = f"""你是一个专业的 AI 资讯编辑，负责从候选文章中精选出最具价值的 AI 热点资讯。

## 任务要求
1. 从以下英文候选文章中精选 **6 条**最重要的 AI 热点资讯
2. 从以下中文候选文章中精选 **4 条**最重要的 AI 热点资讯
3. 对每篇文章：
   - 写一段 **50-80 字**的中文摘要（简洁、准确、突出核心价值）
   - 对于英文文章，额外提供**英文原文摘要**（30-50 words）
4. 优先选择：突破性技术进展 > 重要产品发布 > 行业重大动态 > 研究论文
5. 避免选择：招聘信息、周报汇总、无实质内容的营销文章

## 英文候选文章（共 {len(en_candidates)} 条）
{en_list}

## 中文候选文章（共 {len(zh_candidates)} 条）
{zh_list}

## 输出格式（严格按照 JSON 格式输出，不要有任何其他文字）
{{
  "en_articles": [
    {{
      "index": 1,
      "title_en": "原英文标题",
      "title_zh": "中文翻译标题",
      "summary_zh": "中文摘要（50-80字）",
      "summary_en": "English summary (30-50 words)",
      "source": "来源名称",
      "link": "原文链接",
      "category": "技术突破/产品发布/行业动态/学术研究"
    }}
  ],
  "zh_articles": [
    {{
      "index": 1,
      "title": "文章标题",
      "summary_zh": "中文摘要（50-80字）",
      "source": "来源名称",
      "link": "原文链接",
      "category": "技术突破/产品发布/行业动态/学术研究"
    }}
  ]
}}"""
    return prompt


def call_llm_for_selection(
    en_candidates: list[Article],
    zh_candidates: list[Article],
) -> Optional[dict]:
    """调用 LLM 进行热点筛选和摘要生成。"""
    client = _get_llm_client()
    prompt = build_llm_prompt(en_candidates, zh_candidates)

    logger.info(f"Calling LLM ({LLM_MODEL}) for article selection...")
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是一个专业的 AI 资讯编辑助手，擅长从大量资讯中提炼最有价值的内容。请严格按照 JSON 格式输出结果。",
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        logger.info(
            f"LLM returned {len(result.get('en_articles', []))} EN + "
            f"{len(result.get('zh_articles', []))} ZH articles"
        )
        return result
    except json.JSONDecodeError as e:
        logger.error(f"LLM response JSON parse error: {e}")
        return None
    except Exception as e:
        logger.error(f"LLM API call failed: {e}")
        return None


def fallback_selection(
    en_candidates: list[Article],
    zh_candidates: list[Article],
) -> dict:
    """当 LLM 调用失败时的降级方案：直接使用原始数据。"""
    logger.warning("Using fallback selection (no LLM summarization)")
    en_selected = []
    for a in en_candidates[:TARGET_EN]:
        en_selected.append({
            "index": len(en_selected) + 1,
            "title_en": a.title,
            "title_zh": a.title,  # 无翻译
            "summary_zh": a.summary[:100] if a.summary else "暂无摘要",
            "summary_en": a.summary[:100] if a.summary else "No summary available.",
            "source": a.source,
            "link": a.link,
            "category": "行业动态",
        })
    zh_selected = []
    for a in zh_candidates[:TARGET_ZH]:
        zh_selected.append({
            "index": len(zh_selected) + 1,
            "title": a.title,
            "summary_zh": a.summary[:100] if a.summary else "暂无摘要",
            "source": a.source,
            "link": a.link,
            "category": "行业动态",
        })
    return {"en_articles": en_selected, "zh_articles": zh_selected}


def process_articles(raw_articles: dict[str, list[Article]]) -> dict:
    """
    主处理流程：
    1. 去重
    2. 初步排序
    3. LLM 精选 + 摘要生成
    返回结构化的精选结果。
    """
    en_raw = raw_articles.get("en", [])
    zh_raw = raw_articles.get("zh", [])

    logger.info(f"Processing {len(en_raw)} EN + {len(zh_raw)} ZH articles")

    # 去重
    en_unique = deduplicate(en_raw)
    zh_unique = deduplicate(zh_raw)
    logger.info(f"After dedup: {len(en_unique)} EN + {len(zh_unique)} ZH")

    # 初步排序，取候选集
    en_candidates = pre_rank(en_unique, top_n=20)
    zh_candidates = pre_rank(zh_unique, top_n=15)

    # LLM 精选
    result = call_llm_for_selection(en_candidates, zh_candidates)

    if not result or not result.get("en_articles") or not result.get("zh_articles"):
        result = fallback_selection(en_candidates, zh_candidates)

    # 确保数量限制
    result["en_articles"] = result["en_articles"][:TARGET_EN]
    result["zh_articles"] = result["zh_articles"][:TARGET_ZH]

    return result


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)

    # 测试用：从 scraper 获取数据
    sys.path.insert(0, "/home/ubuntu/ai_news_bot")
    from scraper import fetch_all_articles

    raw = fetch_all_articles()
    result = process_articles(raw)

    print("\n=== 精选英文资讯 ===")
    for item in result.get("en_articles", []):
        print(f"\n[{item['source']}] {item['title_en']}")
        print(f"  中文标题: {item['title_zh']}")
        print(f"  中文摘要: {item['summary_zh']}")
        print(f"  English: {item['summary_en']}")
        print(f"  链接: {item['link']}")

    print("\n=== 精选中文资讯 ===")
    for item in result.get("zh_articles", []):
        print(f"\n[{item['source']}] {item['title']}")
        print(f"  摘要: {item['summary_zh']}")
        print(f"  链接: {item['link']}")
