"""
消息面分析器 — 抓取个股新闻、公告及市场快讯

数据源：
1. 东方财富搜索 API — 个股相关新闻（标题+摘要+时间+来源）
2. 东方财富公告 API — 公司公告（财报、股权、分红等）
3. 新浪 7x24 财经快讯 — 宏观/板块级消息

所有数据汇总后交给 LLM 做情绪分析。
"""

import os
import json
import subprocess
import urllib.parse
from datetime import datetime, timedelta


def _clear_proxy():
    for key in ["http_proxy", "https_proxy", "all_proxy",
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        os.environ.pop(key, None)


def _curl_get(url: str, timeout: int = 10) -> str:
    """通用 curl GET 请求，绕过代理，返回响应文本"""
    result = subprocess.run(
        [
            "curl", "-s", "-m", str(timeout),
            "--noproxy", "*",
            "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            url,
        ],
        capture_output=True, text=True, timeout=timeout + 5,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


class NewsAnalyzer:
    """个股消息面采集器"""

    def __init__(self, code: str, name: str = ""):
        self.code = code
        self.name = name
        # 判断 sh/sz
        prefix = "sh" if code.startswith(("6", "9")) else "sz"
        self.symbol = f"{prefix}{code}"

    def fetch_all(self) -> dict:
        """采集全部消息面数据"""
        _clear_proxy()
        result = {
            "stock_news": [],
            "announcements": [],
            "market_news": [],
        }

        # 并行采集（这里顺序执行，每个有超时保护）
        try:
            result["stock_news"] = self._fetch_stock_news()
        except Exception as e:
            print(f"  ⚠️ 个股新闻获取失败: {e}")

        try:
            result["announcements"] = self._fetch_announcements()
        except Exception as e:
            print(f"  ⚠️ 公告获取失败: {e}")

        try:
            result["market_news"] = self._fetch_market_news()
        except Exception as e:
            print(f"  ⚠️ 市场快讯获取失败: {e}")

        total = sum(len(v) for v in result.values())
        print(f"  📰 消息面采集完成: {len(result['stock_news'])}条新闻 + "
              f"{len(result['announcements'])}条公告 + "
              f"{len(result['market_news'])}条快讯 = 共{total}条")

        return result

    # ──────────────────────────────────────
    # 1. 东方财富搜索 — 个股相关新闻
    # ──────────────────────────────────────

    def _fetch_stock_news(self, num: int = 10) -> list[dict]:
        """
        从东方财富搜索 API 获取个股相关新闻
        返回: [{title, content, date, source, url}, ...]
        """
        keyword = self.name if self.name else self.code
        param = {
            "uid": "",
            "keyword": keyword,
            "type": ["cmsArticleWebOld"],
            "client": "web",
            "clientType": "web",
            "clientVersion": "curr",
            "param": {
                "cmsArticleWebOld": {
                    "searchScope": "default",
                    "sort": "default",
                    "pageIndex": 1,
                    "pageSize": num,
                    "preTag": "",
                    "postTag": "",
                }
            },
        }
        encoded = urllib.parse.quote(json.dumps(param, ensure_ascii=False))
        url = f"https://search-api-web.eastmoney.com/search/jsonp?cb=x&param={encoded}"

        raw = _curl_get(url)
        if not raw:
            return []

        # 去掉 JSONP 回调: x({...})
        if raw.startswith("x(") and raw.endswith(")"):
            raw = raw[2:-1]

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        articles = data.get("result", {}).get("cmsArticleWebOld", [])
        news_list = []
        for a in articles:
            news_list.append({
                "title": a.get("title", ""),
                "content": a.get("content", "")[:200],  # 摘要截断
                "date": a.get("date", ""),
                "source": a.get("mediaName", ""),
                "url": a.get("url", ""),
            })
        return news_list

    # ──────────────────────────────────────
    # 2. 东方财富公告 API — 公司公告
    # ──────────────────────────────────────

    def _fetch_announcements(self, num: int = 5) -> list[dict]:
        """
        获取公司最新公告
        返回: [{title, date, type}, ...]
        """
        url = (
            f"https://np-anotice-stock.eastmoney.com/api/security/ann?"
            f"page_size={num}&page_index=1&ann_type=A"
            f"&stock_list={self.code}&sr=-1&source=web"
        )

        raw = _curl_get(url)
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        ann_list = []
        items = data.get("data", {}).get("list", [])
        for item in items:
            title = item.get("title_ch") or item.get("title", "")
            date = item.get("notice_date", "")[:10]
            columns = item.get("columns", [])
            ann_type = columns[0].get("column_name", "") if columns else ""
            ann_list.append({
                "title": title,
                "date": date,
                "type": ann_type,
            })
        return ann_list

    # ──────────────────────────────────────
    # 3. 新浪 7x24 财经快讯 — 宏观/板块
    # ──────────────────────────────────────

    def _fetch_market_news(self, num: int = 15) -> list[dict]:
        """
        获取最近的市场实时快讯（7x24）
        会从中筛选与本股票/所在行业相关的条目
        返回: [{content, date}, ...]
        """
        url = (
            f"https://zhibo.sina.com.cn/api/zhibo/feed?"
            f"page=1&page_size={num * 3}&zhibo_id=152"
        )

        raw = _curl_get(url)
        if not raw:
            return []

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []

        feed_list = data.get("result", {}).get("data", {}).get("feed", {}).get("list", [])

        # 关键词过滤：股票名、代码、所在行业等
        keywords = {self.code, self.name}
        # 加入常见关联词
        if self.name:
            # 取名称前两个字作为模糊匹配
            if len(self.name) >= 2:
                keywords.add(self.name[:2])

        news_list = []
        for item in feed_list:
            text = item.get("rich_text", "")
            date = item.get("create_time", "")

            # 按关键词过滤相关新闻
            matched = any(kw in text for kw in keywords if kw)
            if matched:
                news_list.append({
                    "content": text[:300],
                    "date": date,
                })

        # 如果没有匹配到个股新闻，返回最新 5 条宏观快讯供 LLM 参考
        if not news_list:
            for item in feed_list[:5]:
                news_list.append({
                    "content": item.get("rich_text", "")[:300],
                    "date": item.get("create_time", ""),
                })

        return news_list[:num]


def format_news_for_prompt(news_data: dict) -> str:
    """
    将消息面数据格式化为 LLM prompt 中的文本段落
    """
    sections = []

    # 个股新闻
    stock_news = news_data.get("stock_news", [])
    if stock_news:
        lines = ["### 个股相关新闻（最新）"]
        for i, n in enumerate(stock_news, 1):
            lines.append(f"{i}. 【{n['date'][:10]}】{n['title']}")
            if n.get("content"):
                lines.append(f"   摘要: {n['content']}")
            if n.get("source"):
                lines.append(f"   来源: {n['source']}")
        sections.append("\n".join(lines))

    # 公司公告
    announcements = news_data.get("announcements", [])
    if announcements:
        lines = ["### 公司公告"]
        for i, a in enumerate(announcements, 1):
            type_tag = f"[{a['type']}] " if a.get("type") else ""
            lines.append(f"{i}. 【{a['date']}】{type_tag}{a['title']}")
        sections.append("\n".join(lines))

    # 市场快讯
    market_news = news_data.get("market_news", [])
    if market_news:
        lines = ["### 市场/板块快讯"]
        for i, m in enumerate(market_news, 1):
            lines.append(f"{i}. 【{m['date'][:16]}】{m['content']}")
        sections.append("\n".join(lines))

    if not sections:
        return "（未获取到消息面数据）"

    return "\n\n".join(sections)
