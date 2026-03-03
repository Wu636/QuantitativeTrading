"""
金融分析 Agent — 采集数据 → 喂给大模型 → 流式输出专业分析报告

流程：
1. TechnicalAnalyzer 计算全部技术指标 & 压力/支撑位
2. FundamentalAnalyzer 获取实时基本面估值数据
3. 将数据打包为结构化 JSON，作为 prompt 发送给 LLM
4. LLM 输出完整的多维度分析报告（支持 SSE 流式）
"""

import json
import traceback
from data.fetcher import DataFetcher
from .technical import TechnicalAnalyzer
from .fundamental import FundamentalAnalyzer
from .news import NewsAnalyzer, format_news_for_prompt
from .llm_client import call_llm


# ──────────────────────────────────────
# 系统提示词
# ──────────────────────────────────────

SYSTEM_PROMPT = """你是一位拥有 20 年A股实战经验的资深金融分析师，擅长技术分析、基本面分析和市场情绪判断。

## 输出要求
请严格按照以下 Markdown 格式输出分析报告，每一节的标题不可省略：

### 📊 综合评级
给出一句话总结性评级（如"短线偏多，中线震荡"），并用 ⭐ 表示推荐度（1-5星）。

### 📈 技术面分析
- 分析均线系统排列状态（多头/空头/缠绕），判断中短期趋势
- 分析 MACD、RSI、KDJ 组合信号，判断动能和超买超卖
- 分析量价关系（放量/缩量 + 涨跌配合）
- 分析布林带位置

### 💰 基本面分析
- 分析估值水平（PE/PB/ROE），与行业对比是否合理
- 分析市值和流动性
- 点评盈利能力

### � 消息面与市场情绪
- 解读最近的个股新闻/公告，判断利好还是利空
- 分析市场热点是否与该股相关（概念、板块联动）
- 综合成交量、龙虎榜、融资客动向等判断市场情绪
- 给出情绪偏向（恐慌/谨慎/中性/乐观/狂热）

### �📐 关键价位
- **压力位**：列出 2-3 个关键压力位及其来源（如"MA60 在 XX 元"）
- **支撑位**：列出 2-3 个关键支撑位及其来源
- 标明距离当前价的百分比

### 🎯 操作建议
- 给出明确的操作方向（买入/观望/卖出/持有）
- 给出具体的建仓价位区间
- 给出止损价位和止盈目标价
- 给出仓位建议（首仓比例、加仓条件）
- 给出持仓周期建议

### ⚠️ 风险提示
- 列出当前持仓的主要风险点
- 需要关注的事件或时间节点

## 分析原则
1. 数据驱动：所有结论必须基于提供的数据，标明具体数值
2. 客观平衡：多空两面都要分析，不要只看一面
3. 实用优先：建议必须可操作，给出具体价位而非笼统描述
4. 风险意识：始终提醒风险，给出止损方案
5. 不要编造数据中没有的信息
6. 消息面分析要区分已兑现利好和未来预期，避免"利好出尽"陷阱"""


class StockAnalyst:
    """个股综合分析 Agent — 数据采集 + LLM 分析"""

    def collect_data(self, code: str, days: int = 365) -> dict:
        """
        采集指定股票的全部数据（技术面 + 基本面），
        返回结构化字典，供后续喂给 LLM。
        """
        report = {"code": code, "status": "ok"}

        # ===== 1. 基本面数据 =====
        try:
            fa = FundamentalAnalyzer(code)
            report["fundamental"] = fa.analyze()
            report["name"] = report["fundamental"].get("name", code)
        except Exception as e:
            traceback.print_exc()
            report["fundamental"] = {"error": str(e)}
            report["name"] = code

        # ===== 2. 技术面数据 =====
        try:
            fetcher = DataFetcher()
            from datetime import datetime, timedelta
            end = datetime.now().strftime("%Y%m%d")
            start = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            df = fetcher.get_stock_daily(code, start_date=start, end_date=end)

            ta = TechnicalAnalyzer(df)
            report["technical"] = ta.analyze()
        except Exception as e:
            traceback.print_exc()
            report["technical"] = {"error": str(e)}

        # ===== 3. 消息面数据 =====
        try:
            name = report.get("name", "")
            na = NewsAnalyzer(code, name)
            report["news"] = na.fetch_all()
        except Exception as e:
            traceback.print_exc()
            report["news"] = {"error": str(e)}

        return report

    def build_prompt(self, data: dict) -> str:
        """
        将采集到的数据构造为 LLM 的用户 prompt
        """
        code = data.get("code", "")
        name = data.get("name", code)

        # 把数据 dict 转为格式化 JSON（方便 LLM 解读）
        tech_json = json.dumps(data.get("technical", {}), ensure_ascii=False, indent=2, default=str)
        fund_json = json.dumps(data.get("fundamental", {}), ensure_ascii=False, indent=2, default=str)

        # 消息面格式化为文本
        news_data = data.get("news", {})
        if isinstance(news_data, dict) and "error" not in news_data:
            news_text = format_news_for_prompt(news_data)
        else:
            news_text = "（消息面数据获取失败）"

        prompt = f"""请对以下A股个股进行全方位专业分析：

## 股票信息
- 代码：{code}
- 名称：{name}

## 技术面数据
```json
{tech_json}
```

## 基本面数据
```json
{fund_json}
```

## 消息面数据
{news_text}

请基于以上全部数据（技术面+基本面+消息面），按照要求的格式输出完整的分析报告。特别注意消息面对情绪和短期走势的影响。"""

        return prompt

    async def analyze_stream(self, code: str, days: int = 365):
        """
        流式分析 — 采集数据后调用 LLM，yield 每个 token 片段。
        前端通过 SSE 接收实现打字机效果。
        """
        # 1. 采集数据
        print(f"🔍 正在采集 {code} 的数据...")
        data = self.collect_data(code, days)

        # 2. 构造 prompt
        user_prompt = self.build_prompt(data)
        print(f"📡 数据采集完毕，正在调用 LLM 分析...")

        # 3. 流式调用 LLM
        stream_gen = await call_llm(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.3,
            max_tokens=4096,
            stream=True,
        )
        async for chunk in stream_gen:
            yield chunk

    async def analyze(self, code: str, days: int = 365) -> dict:
        """
        非流式分析 — 返回完整报告字典（含原始数据 + LLM 分析文本）。
        """
        # 1. 采集数据
        data = self.collect_data(code, days)

        # 2. 构造 prompt & 调用 LLM
        user_prompt = self.build_prompt(data)

        try:
            llm_report = await call_llm(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.3,
                max_tokens=4096,
                stream=False,
            )
        except Exception as e:
            llm_report = f"⚠️ LLM 调用失败: {e}"

        return {
            "code": data.get("code"),
            "name": data.get("name"),
            "fundamental": data.get("fundamental"),
            "technical": data.get("technical"),
            "llm_report": llm_report,
        }

