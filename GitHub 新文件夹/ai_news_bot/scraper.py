"""
AI 资讯抓取模块
支持渠道：
  英文 (60%): Hacker News, Reddit (r/MachineLearning, r/artificial, r/LocalLLaMA), ArXiv
  中文 (40%): 36氪 AI, 机器之心, 量子位, 知乎 AI 话题
"""

import re
import time
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; AINewsBot/1.0; +https://github.com/your-repo)"
    )
}
REQUEST_TIMEOUT = 15  # seconds


@dataclass
class Article:
    title: str
    link: str
    source: str
    language: str  # "en" or "zh"
    # Priority: social > community > blog > academic
    # 1=social, 2=community, 3=blog, 4=academic
    priority: int = 3
    published: Optional[str] = None
    summary: str = ""
    score: int = 0  # engagement score (upvotes, comments, etc.)
    tags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "link": self.link,
            "source": self.source,
            "language": self.language,
            "priority": self.priority,
            "published": self.published,
            "summary": self.summary,
            "score": self.score,
            "tags": self.tags,
        }


# ─────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────

def safe_get(url: str, params: dict = None, timeout: int = REQUEST_TIMEOUT) -> Optional[requests.Response]:
    """HTTP GET with error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as e:
        logger.warning(f"GET {url} failed: {e}")
        return None


def parse_rss(url: str) -> list[dict]:
    """Parse an RSS/Atom feed and return list of {title, link, summary, published}."""
    resp = safe_get(url)
    if not resp:
        return []
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        logger.warning(f"RSS parse error for {url}: {e}")
        return []

    ns = {
        "atom": "http://www.w3.org/2005/Atom",
        "dc": "http://purl.org/dc/elements/1.1/",
        "content": "http://purl.org/rss/1.0/modules/content/",
    }
    items = []

    # RSS 2.0
    for item in root.findall(".//item"):
        title = item.findtext("title", "").strip()
        link = item.findtext("link", "").strip()
        summary = item.findtext("description", "").strip()
        published = item.findtext("pubDate", "") or item.findtext("dc:date", "", ns)
        if title and link:
            items.append({"title": title, "link": link, "summary": summary, "published": published})

    # Atom
    if not items:
        for entry in root.findall("atom:entry", ns):
            title = entry.findtext("atom:title", "", ns).strip()
            link_el = entry.find("atom:link", ns)
            link = link_el.get("href", "") if link_el is not None else ""
            summary = entry.findtext("atom:summary", "", ns).strip()
            published = entry.findtext("atom:published", "", ns)
            if title and link:
                items.append({"title": title, "link": link, "summary": summary, "published": published})

    return items


def clean_html(text: str) -> str:
    """Strip HTML tags from text."""
    return BeautifulSoup(text, "html.parser").get_text(separator=" ").strip()


# ─────────────────────────────────────────────
# English Sources
# ─────────────────────────────────────────────

def fetch_hackernews(limit: int = 30) -> list[Article]:
    """Fetch top AI-related stories from Hacker News via official API."""
    logger.info("Fetching Hacker News top stories...")
    articles = []

    resp = safe_get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not resp:
        return articles

    story_ids = resp.json()[:100]  # top 100

    ai_keywords = [
        "ai", "llm", "gpt", "claude", "gemini", "openai", "anthropic",
        "machine learning", "deep learning", "neural", "transformer",
        "model", "inference", "agent", "rag", "diffusion", "mistral",
        "llama", "chatbot", "artificial intelligence", "ml ", "nlp",
        "hugging face", "langchain", "vector", "embedding", "fine-tun",
    ]

    count = 0
    for sid in story_ids:
        if count >= limit:
            break
        item_resp = safe_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json")
        if not item_resp:
            continue
        item = item_resp.json()
        if not item or item.get("type") != "story":
            continue
        title = item.get("title", "").lower()
        url = item.get("url", f"https://news.ycombinator.com/item?id={sid}")
        score = item.get("score", 0)

        if any(kw in title for kw in ai_keywords) and score >= 50:
            articles.append(Article(
                title=item.get("title", ""),
                link=url,
                source="Hacker News",
                language="en",
                priority=2,  # community
                published=datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc).isoformat(),
                summary="",
                score=score,
                tags=["HackerNews"],
            ))
            count += 1
        time.sleep(0.05)  # rate limit

    logger.info(f"Hacker News: fetched {len(articles)} articles")
    return articles


def fetch_reddit(subreddits: list[str] = None, limit: int = 20) -> list[Article]:
    """Fetch hot posts from Reddit AI subreddits via RSS."""
    if subreddits is None:
        subreddits = ["MachineLearning", "artificial", "LocalLLaMA", "singularity"]

    articles = []
    for sub in subreddits:
        url = f"https://www.reddit.com/r/{sub}/hot.rss?limit=25"
        items = parse_rss(url)
        for item in items[:limit]:
            title = item["title"]
            # Skip meta posts
            if any(x in title.lower() for x in ["weekly thread", "discussion thread", "career", "job"]):
                continue
            articles.append(Article(
                title=title,
                link=item["link"],
                source=f"Reddit r/{sub}",
                language="en",
                priority=1,  # social media
                published=item.get("published", ""),
                summary=clean_html(item.get("summary", ""))[:300],
                score=0,
                tags=["Reddit", sub],
            ))
        logger.info(f"Reddit r/{sub}: fetched {len(items)} articles")
        time.sleep(1)

    return articles


def fetch_arxiv(categories: list[str] = None, max_results: int = 20) -> list[Article]:
    """Fetch latest papers from ArXiv via RSS feed."""
    if categories is None:
        categories = ["cs.AI", "cs.LG", "cs.CL"]

    articles = []
    for cat in categories:
        url = f"https://rss.arxiv.org/rss/{cat}"
        items = parse_rss(url)
        for item in items[:max_results]:
            articles.append(Article(
                title=item["title"].replace("\n", " ").strip(),
                link=item["link"],
                source=f"ArXiv ({cat})",
                language="en",
                priority=4,  # academic
                published=item.get("published", ""),
                summary=clean_html(item.get("summary", ""))[:400],
                score=0,
                tags=["ArXiv", cat],
            ))
        logger.info(f"ArXiv {cat}: fetched {len(items)} articles")
        time.sleep(0.5)

    return articles


def fetch_openai_blog(limit: int = 10) -> list[Article]:
    """Fetch OpenAI blog posts via RSS."""
    logger.info("Fetching OpenAI blog...")
    url = "https://openai.com/blog/rss.xml"
    items = parse_rss(url)
    articles = []
    for item in items[:limit]:
        articles.append(Article(
            title=item["title"],
            link=item["link"],
            source="OpenAI Blog",
            language="en",
            priority=3,  # official blog
            published=item.get("published", ""),
            summary=clean_html(item.get("summary", ""))[:400],
            score=0,
            tags=["OpenAI", "Blog"],
        ))
    logger.info(f"OpenAI Blog: fetched {len(articles)} articles")
    return articles


def fetch_huggingface_blog(limit: int = 10) -> list[Article]:
    """Fetch Hugging Face blog posts via RSS."""
    logger.info("Fetching Hugging Face blog...")
    url = "https://huggingface.co/blog/feed.xml"
    items = parse_rss(url)
    articles = []
    for item in items[:limit]:
        articles.append(Article(
            title=item["title"],
            link=item["link"],
            source="Hugging Face Blog",
            language="en",
            priority=3,  # official blog
            published=item.get("published", ""),
            summary=clean_html(item.get("summary", ""))[:400],
            score=0,
            tags=["HuggingFace", "Blog"],
        ))
    logger.info(f"HuggingFace Blog: fetched {len(articles)} articles")
    return articles


# ─────────────────────────────────────────────
# Chinese Sources
# ─────────────────────────────────────────────

def fetch_36kr_ai(limit: int = 20) -> list[Article]:
    """Fetch 36Kr AI channel articles via RSS."""
    logger.info("Fetching 36Kr AI...")
    # 36Kr RSS feed for AI topic
    url = "https://36kr.com/feed"
    items = parse_rss(url)
    articles = []
    ai_keywords_zh = ["AI", "人工智能", "大模型", "LLM", "GPT", "机器学习", "深度学习",
                       "智能", "算法", "神经网络", "自动驾驶", "生成式", "Sora", "Claude",
                       "Gemini", "OpenAI", "Anthropic", "百度", "阿里", "腾讯", "华为"]
    for item in items:
        if len(articles) >= limit:
            break
        title = item["title"]
        if any(kw in title for kw in ai_keywords_zh):
            articles.append(Article(
                title=title,
                link=item["link"],
                source="36氪",
                language="zh",
                priority=2,  # community/media
                published=item.get("published", ""),
                summary=clean_html(item.get("summary", ""))[:300],
                score=0,
                tags=["36氪", "AI"],
            ))
    logger.info(f"36Kr AI: fetched {len(articles)} articles")
    return articles


def fetch_jiqizhixin(limit: int = 15) -> list[Article]:
    """Fetch 机器之心 (Synced) articles via web scraping."""
    logger.info("Fetching 机器之心...")
    articles = []
    try:
        resp = safe_get("https://www.jiqizhixin.com/articles")
        if not resp:
            return articles
        soup = BeautifulSoup(resp.text, "html.parser")
        # Find article cards
        cards = soup.select("a.article-item-title") or soup.select(".article-item a[href*='/articles/']") or soup.select("h2 a")
        seen = set()
        for card in cards[:limit * 2]:
            title = card.get_text(strip=True)
            href = card.get("href", "")
            if not href.startswith("http"):
                href = "https://www.jiqizhixin.com" + href
            if title and href not in seen and len(title) > 5:
                seen.add(href)
                articles.append(Article(
                    title=title,
                    link=href,
                    source="机器之心",
                    language="zh",
                    priority=2,
                    published="",
                    summary="",
                    score=0,
                    tags=["机器之心"],
                ))
            if len(articles) >= limit:
                break
    except Exception as e:
        logger.warning(f"机器之心 scrape error: {e}")
    logger.info(f"机器之心: fetched {len(articles)} articles")
    return articles


def fetch_leiphone(limit: int = 15) -> list[Article]:
    """Fetch 雷锋网 AI articles via RSS."""
    logger.info("Fetching 雷锋网...")
    url = "https://www.leiphone.com/feed"
    items = parse_rss(url)
    articles = []
    ai_keywords_zh = ["AI", "人工智能", "大模型", "LLM", "GPT", "机器学习", "深度学习",
                       "智能", "算法", "神经网络", "生成式", "OpenAI", "Anthropic"]
    for item in items:
        if len(articles) >= limit:
            break
        title = item["title"]
        if any(kw in title for kw in ai_keywords_zh):
            articles.append(Article(
                title=title,
                link=item["link"],
                source="雷锋网",
                language="zh",
                priority=2,
                published=item.get("published", ""),
                summary=clean_html(item.get("summary", ""))[:300],
                score=0,
                tags=["雷锋网", "AI"],
            ))
    logger.info(f"雷锋网: fetched {len(articles)} articles")
    return articles


def fetch_oschina_ai(limit: int = 15) -> list[Article]:
    """Fetch 开源中国 AI 资讯 via RSS as a replacement for Zhihu."""
    logger.info("Fetching 开源中国 AI...")
    url = "https://www.oschina.net/news/rss"
    items = parse_rss(url)
    articles = []
    ai_keywords_zh = ["AI", "人工智能", "大模型", "LLM", "GPT", "机器学习", "深度学习",
                       "ChatGPT", "Claude", "Gemini", "Sora", "算法", "神经网络",
                       "OpenAI", "Anthropic", "生成式", "智能体", "向量"]
    for item in items:
        if len(articles) >= limit:
            break
        title = item["title"]
        if any(kw in title for kw in ai_keywords_zh):
            articles.append(Article(
                title=title,
                link=item["link"],
                source="开源中国",
                language="zh",
                priority=2,
                published=item.get("published", ""),
                summary=clean_html(item.get("summary", ""))[:300],
                score=0,
                tags=["开源中国", "AI"],
            ))
    logger.info(f"开源中国: fetched {len(articles)} articles")
    return articles


def fetch_infoq_ai(limit: int = 15) -> list[Article]:
    """Fetch InfoQ 中文 AI 资讯 via RSS."""
    logger.info("Fetching InfoQ AI...")
    url = "https://www.infoq.cn/feed"
    items = parse_rss(url)
    articles = []
    ai_keywords_zh = ["AI", "人工智能", "大模型", "LLM", "GPT", "机器学习", "深度学习",
                       "ChatGPT", "Claude", "Gemini", "算法", "神经网络", "生成式"]
    for item in items:
        if len(articles) >= limit:
            break
        title = item["title"]
        if any(kw in title for kw in ai_keywords_zh):
            articles.append(Article(
                title=title,
                link=item["link"],
                source="InfoQ",
                language="zh",
                priority=2,
                published=item.get("published", ""),
                summary=clean_html(item.get("summary", ""))[:300],
                score=0,
                tags=["InfoQ", "AI"],
            ))
    logger.info(f"InfoQ: fetched {len(articles)} articles")
    return articles


def fetch_sspai_ai(limit: int = 10) -> list[Article]:
    """Fetch 少数派 AI articles via RSS."""
    logger.info("Fetching 少数派...")
    url = "https://sspai.com/feed"
    items = parse_rss(url)
    articles = []
    ai_keywords_zh = ["AI", "人工智能", "大模型", "LLM", "GPT", "ChatGPT", "Claude",
                       "Gemini", "机器学习", "生成式", "自动化", "效率"]
    for item in items:
        if len(articles) >= limit:
            break
        title = item["title"]
        if any(kw in title for kw in ai_keywords_zh):
            articles.append(Article(
                title=title,
                link=item["link"],
                source="少数派",
                language="zh",
                priority=2,
                published=item.get("published", ""),
                summary=clean_html(item.get("summary", ""))[:300],
                score=0,
                tags=["少数派", "AI"],
            ))
    logger.info(f"少数派: fetched {len(articles)} articles")
    return articles


# ─────────────────────────────────────────────
# Main aggregation entry point
# ─────────────────────────────────────────────

def fetch_all_articles() -> dict[str, list[Article]]:
    """
    Fetch articles from all sources.
    Returns dict with keys 'en' and 'zh'.
    """
    en_articles: list[Article] = []
    zh_articles: list[Article] = []

    # English sources
    en_articles.extend(fetch_hackernews(limit=30))
    en_articles.extend(fetch_reddit())
    en_articles.extend(fetch_arxiv())
    en_articles.extend(fetch_openai_blog())
    en_articles.extend(fetch_huggingface_blog())

    # Chinese sources
    zh_articles.extend(fetch_36kr_ai())
    zh_articles.extend(fetch_jiqizhixin())
    zh_articles.extend(fetch_leiphone())
    zh_articles.extend(fetch_oschina_ai())
    zh_articles.extend(fetch_infoq_ai())
    zh_articles.extend(fetch_sspai_ai())

    logger.info(f"Total fetched: {len(en_articles)} EN, {len(zh_articles)} ZH")
    return {"en": en_articles, "zh": zh_articles}


if __name__ == "__main__":
    results = fetch_all_articles()
    print(f"\n=== English Articles ({len(results['en'])}) ===")
    for a in results["en"][:5]:
        print(f"  [{a.source}] {a.title[:80]}")
    print(f"\n=== Chinese Articles ({len(results['zh'])}) ===")
    for a in results["zh"][:5]:
        print(f"  [{a.source}] {a.title[:80]}")
