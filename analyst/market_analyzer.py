"""
市场状态分析引擎 - 支持纯量化模式与 LLM 增强模式
"""

import json
import traceback
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

from data.fetcher import DataFetcher
from stock_picker.templates import list_all_templates
from analyst.news import NewsAnalyzer, format_news_for_prompt
from analyst.llm_client import call_llm

# 四维权重
WEIGHTS = {
    "trend": 0.35,        # 趋势
    "volatility": 0.25,   # 波动
    "sentiment": 0.25,    # 情绪
    "capital": 0.15       # 资金
}

# 五档状态定义
REGIMES = [
    {"level": 1, "name": "恐慌下跌", "min_score": 0, "max_score": 20, "desc": "市场极度悲观，建议空仓观望或极端左侧抄底"},
    {"level": 2, "name": "弱势调整", "min_score": 20, "max_score": 40, "desc": "市场处于跌势或低位震荡，防御为主，可关注困境反转"},
    {"level": 3, "name": "震荡整理", "min_score": 40, "max_score": 60, "desc": "市场无明显单边趋势，操作难度大，适合价值回归或高抛低吸"},
    {"level": 4, "name": "温和上涨", "min_score": 60, "max_score": 80, "desc": "市场赚钱效应良好，动量趋势为主，适度配置价值"},
    {"level": 5, "name": "强势上涨", "min_score": 80, "max_score": 100, "desc": "市场情绪高昂，趋势明朗，建议顺势全仓追击动量龙头"}
]

SYSTEM_PROMPT = """你是一位拥有 20 年 A 股实战经验的宏观策略分析师。
你的任务是基于我提供的【纯量化市场状态数据】和【最新市场新闻/大盘资金动态】，给出深度的市场解读。

## 输出要求
请严格按以下 Markdown 格式输出：

### 🎯 综合研判
一句话总结当前市场状态及核心驱动力（例如："受稳增长政策超预期影响，市场放量突破，情绪显著回暖"）。

### 📊 量化数据解读
- 解读趋势得分、波动得分、情绪得分、资金得分所反映的真实市场状况。
- 指出当前数据结构中的积极信号与隐患（如"虽然指数上涨，但量能得分偏低，有诱多嫌疑"）。

### 📰 消息面与热点推演
- 梳理最新的宏观、行业重量级新闻，判断政策底/市场底。
- 这两天有哪些题材/板块正受到资金追捧？背后的逻辑是什么？

### 💡 交易策略建议
- **仓位管理**：建议当前保持多少仓位？
- **风格偏好**：当前更适合大盘价值、小盘成长、还是短线打板？
- **推荐策略模板解读**：说明为什么推荐系统给出的选股模板（如为什么这时候该用"困境反转"或"动量趋势"）。
- **防守建议**：需要避开哪些雷区或高位板块？

## 注意事项
1. 你的分析必须与传入的量化数据基调保持一致，不要在数据明显是"恐慌下跌"时硬唱多。
2. 语言要专业、犀利、有实战价值，避免废话。
"""

class MarketAnalyzer:
    """纯量化市场状态分析"""
    
    def __init__(self, days=120):
        self.days = days
        self.fetcher = DataFetcher()

    def _fetch_indices(self) -> dict:
        """获取三大指数数据（使用新浪财经 API，绕过代理问题）"""
        import subprocess, json as _json

        indices = [
            ("sh", "sh000001"),   # 上证指数
            ("sz", "sz399001"),   # 深证成指
            ("hs300", "sh000300"), # 沪深300
        ]

        data = {}
        for key, sina_symbol in indices:
            try:
                url = (
                    f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
                    f"CN_MarketData.getKLineData?"
                    f"symbol={sina_symbol}&scale=240&ma=no&datalen={self.days}"
                )
                result = subprocess.run(
                    [
                        "curl", "-s", "-m", "15",
                        "--noproxy", "*",
                        "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                        "-H", "Referer: https://finance.sina.com.cn/",
                        url,
                    ],
                    capture_output=True, text=True, timeout=20,
                )
                if result.returncode != 0 or not result.stdout.strip():
                    print(f"  ⚠️ 指数 {sina_symbol} curl 请求失败")
                    continue

                raw = result.stdout.strip().replace("'", '"')
                klines = _json.loads(raw)
                if not klines:
                    continue

                rows = []
                for k in klines:
                    rows.append({
                        "date": k["day"][:10],
                        "open": float(k["open"]),
                        "high": float(k["high"]),
                        "low": float(k["low"]),
                        "close": float(k["close"]),
                        "volume": int(float(k["volume"])),
                    })
                df = pd.DataFrame(rows)
                df["date"] = pd.to_datetime(df["date"])
                df = df.set_index("date").sort_index()

                if df.empty:
                    continue

                # 计算 MA 和涨跌幅
                for w in [5, 10, 20, 60]:
                    df[f"ma{w}"] = df["close"].rolling(window=w).mean()
                df["pct_chg"] = df["close"].pct_change() * 100
                data[key] = df
                print(f"  ✅ 指数 {sina_symbol} 获取 {len(df)} 条K线")
            except Exception as e:
                print(f"  ⚠️ 指数 {sina_symbol} 获取失败: {e}")
                continue
        return data

    def _compute_trend_score(self, df_dict: dict) -> float:
        """计算趋势得分 (0-100)"""
        scores = []
        for key, df in df_dict.items():
            if df.empty or len(df) < 60:
                continue
            last = df.iloc[-1]
            score = 50
            # MA 排列
            if pd.notna(last.get("ma5")) and pd.notna(last.get("ma20")):
                if last["ma5"] > last["ma20"]:
                    score += 20
                else:
                    score -= 20
            # 价格站上 MA60
            if pd.notna(last.get("ma60")):
                if last["close"] > last["ma60"]:
                    score += 20
                else:
                    score -= 20
            # 短期涨跌
            if last["pct_chg"] > 0:
                score += 10
            elif last["pct_chg"] < 0:
                score -= 10
            scores.append(max(0, min(100, score)))
        return np.mean(scores) if scores else 50.0

    def _compute_volatility_score(self, df_dict: dict) -> float:
        """计算波动得分 (0-100, 波动越低得分越高，表示适合做趋势)
           不过这里为了与整体匹配：
           如果波动极度萎缩，可能是变盘前夕；
           如果波动大，说明活跃，但若是向下的高波动则得分低。
           我们采用简单ATR与均线的关系
        """
        scores = []
        for key, df in df_dict.items():
            if df.empty or len(df) < 20:
                continue
            # ATR (14)
            tr = pd.concat([
                df['high'] - df['low'],
                (df['high'] - df['close'].shift(1)).abs(),
                (df['low'] - df['close'].shift(1)).abs()
            ], axis=1).max(axis=1)
            atr = tr.rolling(14).mean()
            current_atr_pct = (atr.iloc[-1] / df['close'].iloc[-1]) * 100
            
            # 以 1.5% - 3.0% 为常态基准，较低波动给 60 分，适度高波动给 80，恐慌高波动给 20
            if pd.isna(current_atr_pct):
                score = 50
            elif current_atr_pct < 1.0:
                score = 60 # 极度缩量横盘
            elif 1.0 <= current_atr_pct < 2.5:
                score = 80 # 温和波动
            elif 2.5 <= current_atr_pct < 4.0:
                score = 40 # 剧烈波动
            else:
                score = 10 # 极端波动
            scores.append(score)
        return np.mean(scores) if scores else 50.0

    def _compute_sentiment_score(self, df_dict: dict) -> float:
        """计算情绪得分 (0-100)"""
        scores = []
        for key, df in df_dict.items():
            if df.empty or len(df) < 14:
                continue
            # RSI (14)
            delta = df["close"].diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - 100 / (1 + rs)
            last_rsi = rsi.iloc[-1]
            
            if pd.isna(last_rsi):
                score = 50
            elif last_rsi > 80:
                score = 90
            elif last_rsi > 60:
                score = 70
            elif last_rsi > 40:
                score = 50
            elif last_rsi > 20:
                score = 30
            else:
                score = 10
            scores.append(score)
        return np.mean(scores) if scores else 50.0

    def _compute_capital_score(self, df_dict: dict) -> float:
        """计算资金得分 (0-100)"""
        scores = []
        for key, df in df_dict.items():
            if df.empty or len(df) < 10:
                continue
            vol = df["volume"].iloc[-1]
            vol_ma5 = df["volume"].rolling(5).mean().iloc[-1]
            if pd.isna(vol_ma5) or vol_ma5 == 0:
                score = 50
            else:
                ratio = vol / vol_ma5
                if ratio > 1.5:
                    score = 90 if df["pct_chg"].iloc[-1] > 0 else 30 # 放量上涨/下跌
                elif ratio > 1.0:
                    score = 70 if df["pct_chg"].iloc[-1] > 0 else 40
                elif ratio > 0.8:
                    score = 50
                else:
                    score = 40 # 缩量
            scores.append(score)
        return np.mean(scores) if scores else 50.0

    def _match_templates(self, score: float) -> list:
        """根据市场总分，推荐适合的模板排行"""
        templates = list_all_templates()
        scored_templates = []
        
        for t in templates:
            t_score = 50
            w = t.get("weights", {})
            
            # 如果是强势市场 (score > 60)
            if score >= 60:
                # 偏好动量和资金流入
                t_score += w.get("momentum", 0) * 100
                t_score += w.get("capital_flow", 0) * 50
            # 如果是弱势市场 (score < 40)
            elif score <= 40:
                # 偏好价值和防守
                t_score += w.get("value", 0) * 100
                t_score += w.get("roe", 0) * 50
                t_score -= w.get("momentum", 0) * 50
            # 震荡市
            else:
                # 偏好反转或量价背离
                if t.get("id") == "volume_price_divergence":
                    t_score += 30
                if t.get("id") == "value_reversion":
                    t_score += 20
                    
            scored_templates.append({
                "id": t["id"],
                "name": t["name"],
                "description": t["description"],
                "match_score": round(t_score)
            })
            
        # 降序排序
        scored_templates.sort(key=lambda x: x["match_score"], reverse=True)
        return scored_templates[:3] # 返回前3个

    def analyze(self) -> dict:
        """执行全量化分析"""
        df_dict = self._fetch_indices()
        if not df_dict:
            return {"error": "获取指数数据失败"}
            
        trend = self._compute_trend_score(df_dict)
        volatility = self._compute_volatility_score(df_dict)
        sentiment = self._compute_sentiment_score(df_dict)
        capital = self._compute_capital_score(df_dict)
        
        total_score = (
            trend * WEIGHTS["trend"] +
            volatility * WEIGHTS["volatility"] +
            sentiment * WEIGHTS["sentiment"] +
            capital * WEIGHTS["capital"]
        )
        total_score = round(total_score, 1)
        
        # 匹配档位
        regime = next((r for r in REGIMES if r["min_score"] <= total_score <= r["max_score"]), REGIMES[2])
        
        # 获取最新的收盘数据用于前端展示迷你图
        charts = {}
        for key, df in df_dict.items():
            if not df.empty:
                tail = df.tail(20).copy()
                tail["date"] = tail.index.strftime("%Y-%m-%d")
                charts[key] = tail[["date", "close", "pct_chg"]].to_dict("records")

        return {
            "score": total_score,
            "regime": regime,
            "dimensions": {
                "trend": round(trend, 1),
                "volatility": round(volatility, 1),
                "sentiment": round(sentiment, 1),
                "capital": round(capital, 1)
            },
            "recommendations": self._match_templates(total_score),
            "charts": charts
        }


class MarketAnalyzerLLM(MarketAnalyzer):
    """LLM 增强的市场状态分析"""
    
    def __init__(self, days=120):
        super().__init__(days)
        
    def _build_prompt(self, quant_data: dict, news_data: dict) -> str:
        quant_json = json.dumps({
            "score": quant_data["score"],
            "regime": quant_data["regime"]["name"],
            "dimensions": quant_data["dimensions"],
            "recommendations": quant_data["recommendations"]
        }, ensure_ascii=False, indent=2)
        
        # 只取市场快讯
        market_news = news_data.get("market_news", [])
        if market_news:
            lines = ["### 大盘/宏观市场快讯（最新）"]
            for i, m in enumerate(market_news[:15], 1): # 取前15条
                lines.append(f"{i}. 【{m['date'][:16]}】{m['content']}")
            news_text = "\n".join(lines)
        else:
            news_text = "（未获取到市场快讯）"

        prompt = f"""请对当前A股大盘状态进行全方位深度分析：

## 纯量化分析结果
```json
{quant_json}
```

## 最新市场快讯及宏观消息
{news_text}

请结合量化数据的基础判断和最新的消息面情绪，按照严格的 Markdown 格式输出深度报告。
"""
        return prompt

    async def analyze_stream(self):
        """流式增强分析"""
        print("🔍 正在计算纯量化市场指标...")
        quant_data = self.analyze()
        if "error" in quant_data:
            yield f"⚠️ 量化部分分析出错: {quant_data['error']}"
            return
            
        # yield 特殊标记，传递纯量化结果给前端，前端可先渲染仪表盘
        yield json.dumps({"type": "quant_data", "data": quant_data})
        
        print("📰 正在采集宏观市场快讯...")
        try:
            # Fake code/name to reuse Market News grabber
            na = NewsAnalyzer(code="000001", name="上证指数")
            result = na.fetch_all()
        except Exception as e:
            traceback.print_exc()
            result = {"market_news": []}
            
        print("📡 正在调用 LLM 进行深度分析...")
        user_prompt = self._build_prompt(quant_data, result)
        
        stream_gen = await call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream_gen:
            yield chunk

