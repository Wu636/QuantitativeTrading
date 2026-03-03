"""
技术面分析器 — 计算常用技术指标 & 压力位/支撑位

输入：OHLCV DataFrame (columns: date, open, high, low, close, volume)
输出：技术信号字典
"""

import pandas as pd
import numpy as np


class TechnicalAnalyzer:
    """技术面分析"""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self._compute_indicators()

    # ──────────────────────────────────────
    # 指标计算
    # ──────────────────────────────────────

    def _compute_indicators(self):
        df = self.df
        c = df["close"]

        # 均线
        for w in [5, 10, 20, 60, 120, 250]:
            df[f"ma{w}"] = c.rolling(w).mean()

        # MACD (12, 26, 9)
        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        df["dif"] = ema12 - ema26
        df["dea"] = df["dif"].ewm(span=9, adjust=False).mean()
        df["macd_hist"] = (df["dif"] - df["dea"]) * 2

        # RSI (14)
        delta = c.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        df["rsi"] = 100 - 100 / (1 + rs)

        # KDJ (9, 3, 3)
        low_9 = df["low"].rolling(9).min()
        high_9 = df["high"].rolling(9).max()
        rsv = (c - low_9) / (high_9 - low_9).replace(0, np.nan) * 100
        df["k"] = rsv.ewm(com=2, adjust=False).mean()
        df["d"] = df["k"].ewm(com=2, adjust=False).mean()
        df["j"] = 3 * df["k"] - 2 * df["d"]

        # 布林带 (20, 2)
        df["boll_mid"] = c.rolling(20).mean()
        std20 = c.rolling(20).std()
        df["boll_upper"] = df["boll_mid"] + 2 * std20
        df["boll_lower"] = df["boll_mid"] - 2 * std20

        # ATR (14)
        tr1 = df["high"] - df["low"]
        tr2 = (df["high"] - c.shift(1)).abs()
        tr3 = (df["low"] - c.shift(1)).abs()
        df["atr"] = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1).rolling(14).mean()

        # 成交量均线
        df["vol_ma5"] = df["volume"].rolling(5).mean()
        df["vol_ma20"] = df["volume"].rolling(20).mean()

        self.df = df

    # ──────────────────────────────────────
    # 压力位 / 支撑位
    # ──────────────────────────────────────

    def calc_support_resistance(self) -> dict:
        """
        使用多种方法综合计算支撑位和压力位：
        1. 经典枢轴点 (Pivot Point)
        2. 布林带
        3. 关键均线
        4. 近期高低点
        """
        df = self.df
        last = df.iloc[-1]
        price = last["close"]

        h = last["high"]
        l = last["low"]
        c = last["close"]

        # 经典 Pivot
        pivot = (h + l + c) / 3
        r1 = 2 * pivot - l
        r2 = pivot + (h - l)
        s1 = 2 * pivot - h
        s2 = pivot - (h - l)

        levels = []

        def _add(name, value, kind):
            if pd.notna(value) and value > 0:
                levels.append({"name": name, "price": round(float(value), 2), "kind": kind})

        _add("经典支撑S2", s2, "support")
        _add("经典支撑S1", s1, "support")
        _add("枢轴点", pivot, "pivot")
        _add("经典压力R1", r1, "resistance")
        _add("经典压力R2", r2, "resistance")

        # 布林带
        _add("布林下轨", last.get("boll_lower"), "support")
        _add("布林中轨", last.get("boll_mid"), "pivot")
        _add("布林上轨", last.get("boll_upper"), "resistance")

        # 关键均线
        for w in [5, 10, 20, 60, 120, 250]:
            ma_val = last.get(f"ma{w}")
            if pd.notna(ma_val):
                kind = "support" if ma_val < price else "resistance"
                _add(f"MA{w}", ma_val, kind)

        # 近 60 日高低点
        recent = df.tail(60)
        _add("60日最低", recent["low"].min(), "support")
        _add("60日最高", recent["high"].max(), "resistance")

        # 去重 & 排序
        seen = set()
        unique = []
        for lv in sorted(levels, key=lambda x: x["price"]):
            key = round(lv["price"], 1)
            if key not in seen:
                seen.add(key)
                unique.append(lv)

        return {
            "current_price": round(float(price), 2),
            "levels": unique,
        }

    # ──────────────────────────────────────
    # 趋势 & 信号判断
    # ──────────────────────────────────────

    def analyze(self) -> dict:
        df = self.df
        last = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else last
        price = last["close"]

        signals = []
        score = 0  # -100 ~ +100

        # ─── 均线多空排列 ───
        ma5 = last.get("ma5")
        ma10 = last.get("ma10")
        ma20 = last.get("ma20")
        ma60 = last.get("ma60")

        if pd.notna(ma5) and pd.notna(ma20):
            if ma5 > ma10 > ma20:
                signals.append({"indicator": "均线", "signal": "bullish", "detail": "短期均线多头排列 (MA5>MA10>MA20)"})
                score += 20
            elif ma5 < ma10 < ma20:
                signals.append({"indicator": "均线", "signal": "bearish", "detail": "短期均线空头排列 (MA5<MA10<MA20)"})
                score -= 20
            else:
                signals.append({"indicator": "均线", "signal": "neutral", "detail": "均线交织，方向不明"})

        if pd.notna(ma60):
            if price > ma60:
                signals.append({"indicator": "MA60", "signal": "bullish", "detail": f"股价站上60日线 ({ma60:.2f})，中期趋势偏多"})
                score += 10
            else:
                signals.append({"indicator": "MA60", "signal": "bearish", "detail": f"股价在60日线之下 ({ma60:.2f})，中期趋势偏空"})
                score -= 10

        # ─── MACD ───
        dif = last.get("dif")
        dea = last.get("dea")
        macd_h = last.get("macd_hist")
        prev_macd_h = prev.get("macd_hist")

        if pd.notna(dif) and pd.notna(dea):
            if dif > dea and (pd.isna(prev_macd_h) or prev_macd_h <= 0 < macd_h):
                signals.append({"indicator": "MACD", "signal": "bullish", "detail": "MACD金叉，DIF上穿DEA"})
                score += 15
            elif dif < dea and (pd.isna(prev_macd_h) or prev_macd_h >= 0 > macd_h):
                signals.append({"indicator": "MACD", "signal": "bearish", "detail": "MACD死叉，DIF下穿DEA"})
                score -= 15
            elif dif > 0 and dea > 0:
                signals.append({"indicator": "MACD", "signal": "bullish", "detail": f"MACD零轴之上运行 (DIF={dif:.3f})"})
                score += 5
            elif dif < 0 and dea < 0:
                signals.append({"indicator": "MACD", "signal": "bearish", "detail": f"MACD零轴之下运行 (DIF={dif:.3f})"})
                score -= 5

        # ─── RSI ───
        rsi = last.get("rsi")
        if pd.notna(rsi):
            if rsi > 80:
                signals.append({"indicator": "RSI", "signal": "bearish", "detail": f"RSI={rsi:.1f}，超买区间，警惕回调"})
                score -= 10
            elif rsi < 20:
                signals.append({"indicator": "RSI", "signal": "bullish", "detail": f"RSI={rsi:.1f}，超卖区间，存在反弹机会"})
                score += 10
            elif rsi > 60:
                signals.append({"indicator": "RSI", "signal": "bullish", "detail": f"RSI={rsi:.1f}，偏强"})
                score += 5
            elif rsi < 40:
                signals.append({"indicator": "RSI", "signal": "bearish", "detail": f"RSI={rsi:.1f}，偏弱"})
                score -= 5
            else:
                signals.append({"indicator": "RSI", "signal": "neutral", "detail": f"RSI={rsi:.1f}，中性区间"})

        # ─── KDJ ───
        k_val = last.get("k")
        d_val = last.get("d")
        j_val = last.get("j")
        if pd.notna(j_val):
            if j_val > 100:
                signals.append({"indicator": "KDJ", "signal": "bearish", "detail": f"J值={j_val:.1f}，超买区域"})
                score -= 5
            elif j_val < 0:
                signals.append({"indicator": "KDJ", "signal": "bullish", "detail": f"J值={j_val:.1f}，超卖区域"})
                score += 5

        # ─── 布林带 ───
        boll_upper = last.get("boll_upper")
        boll_lower = last.get("boll_lower")
        if pd.notna(boll_upper) and pd.notna(boll_lower):
            if price >= boll_upper:
                signals.append({"indicator": "BOLL", "signal": "bearish", "detail": "触及布林上轨，短期超买"})
                score -= 5
            elif price <= boll_lower:
                signals.append({"indicator": "BOLL", "signal": "bullish", "detail": "触及布林下轨，短期超卖"})
                score += 5

        # ─── 量能 ───
        vol = last.get("volume", 0)
        vol_ma5 = last.get("vol_ma5")
        vol_ma20 = last.get("vol_ma20")
        if pd.notna(vol_ma5) and vol_ma5 > 0:
            vol_ratio = vol / vol_ma5
            if vol_ratio > 2:
                signals.append({"indicator": "量能", "signal": "bullish" if price > prev["close"] else "bearish",
                                "detail": f"放量{vol_ratio:.1f}倍（vs 5日均量），{'多方发力' if price > prev['close'] else '放量下跌'}"})
                score += 10 if price > prev["close"] else -10
            elif vol_ratio < 0.5:
                signals.append({"indicator": "量能", "signal": "neutral", "detail": f"严重缩量（仅5日均量的{vol_ratio:.0%}），观望为主"})

        # ─── 趋势评级 ───
        score = max(-100, min(100, score))
        if score >= 40:
            trend = "强势看多"
        elif score >= 15:
            trend = "偏多震荡"
        elif score > -15:
            trend = "震荡整理"
        elif score > -40:
            trend = "偏空震荡"
        else:
            trend = "弱势看空"

        return {
            "trend": trend,
            "score": score,
            "signals": signals,
            "indicators": {
                "price": round(float(price), 2),
                "ma5": round(float(ma5), 2) if pd.notna(ma5) else None,
                "ma10": round(float(ma10), 2) if pd.notna(ma10) else None,
                "ma20": round(float(ma20), 2) if pd.notna(ma20) else None,
                "ma60": round(float(ma60), 2) if pd.notna(ma60) else None,
                "rsi": round(float(rsi), 1) if pd.notna(rsi) else None,
                "macd_dif": round(float(dif), 4) if pd.notna(dif) else None,
                "macd_dea": round(float(dea), 4) if pd.notna(dea) else None,
                "kdj_k": round(float(k_val), 1) if pd.notna(k_val) else None,
                "kdj_d": round(float(d_val), 1) if pd.notna(d_val) else None,
                "kdj_j": round(float(j_val), 1) if pd.notna(j_val) else None,
                "atr": round(float(last.get("atr", 0)), 3) if pd.notna(last.get("atr")) else None,
            },
            "support_resistance": self.calc_support_resistance(),
        }
