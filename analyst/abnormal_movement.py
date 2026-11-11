"""
A 股异动与严重异动计算。

核心口径：
区间涨幅偏离值 = 个股 N 日区间累计涨幅 - 对应基准指数 N 日区间累计涨幅
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import pandas as pd


@dataclass(frozen=True)
class BoardRule:
    board: str
    board_name: str
    index_symbol: str
    index_name: str
    ordinary_up: float
    ordinary_down: float
    same_direction_count: int
    has_turnover_rule: bool
    is_st: bool = False


INDEX_RULES = {
    "sh_main": ("sh000002", "上证 A 股指数"),
    "sz_main": ("sz399107", "深证 A 股指数"),
    "chinext": ("sz399102", "创业板综合指数"),
    "star": ("sh000680", "科创板综合指数"),
}


def resolve_board_rule(symbol: str, stock_name: str = "") -> BoardRule:
    code = str(symbol).strip()
    name = stock_name or ""
    is_st = "ST" in name.upper()

    if code.startswith("300"):
        index_symbol, index_name = INDEX_RULES["chinext"]
        return BoardRule("chinext", "创业板", index_symbol, index_name, 30, -30, 3, False)
    if code.startswith("688"):
        index_symbol, index_name = INDEX_RULES["star"]
        return BoardRule("star", "科创板", index_symbol, index_name, 30, -30, 3, False)
    if code.startswith("60"):
        index_symbol, index_name = INDEX_RULES["sh_main"]
        threshold = 12 if is_st else 20
        return BoardRule("sh_main", "沪市主板 ST" if is_st else "沪市主板", index_symbol, index_name, threshold, -threshold, 4, not is_st, is_st)
    if code.startswith("00"):
        index_symbol, index_name = INDEX_RULES["sz_main"]
        threshold = 12 if is_st else 20
        return BoardRule("sz_main", "深市主板 ST" if is_st else "深市主板", index_symbol, index_name, threshold, -threshold, 4, not is_st, is_st)

    index_symbol, index_name = INDEX_RULES["sz_main"]
    return BoardRule("unknown", "未知板块", index_symbol, index_name, 20, -20, 4, False)


def next_business_days(last_date: pd.Timestamp, count: int) -> list[pd.Timestamp]:
    days = []
    current = last_date
    while len(days) < count:
        current = current + timedelta(days=1)
        if current.weekday() < 5:
            days.append(current)
    return days


def _pct_change(df: pd.DataFrame) -> pd.Series:
    if "pct_change" in df.columns:
        pct = pd.to_numeric(df["pct_change"], errors="coerce")
        if pct.notna().sum() > 2:
            return pct
    return pd.to_numeric(df["close"], errors="coerce").pct_change() * 100


def _round(value, digits=2):
    if pd.isna(value):
        return None
    return round(float(value), digits)


def _direction(value: float, up_threshold: float, down_threshold: float) -> str | None:
    if value >= up_threshold:
        return "up"
    if value <= down_threshold:
        return "down"
    return None


def _window_deviation(close: pd.Series, index_close: pd.Series, window: int) -> pd.Series:
    stock_return = close / close.shift(window) - 1
    index_return = index_close / index_close.shift(window) - 1
    return (stock_return - index_return) * 100


def _target_price_for_window(
    stock_base_close: float,
    index_base_close: float,
    future_index_close: float,
    target_deviation: float,
) -> float:
    index_window_pct = future_index_close / index_base_close - 1
    return stock_base_close * (1 + target_deviation / 100 + index_window_pct)


def calculate_abnormal_movement(
    stock_daily: pd.DataFrame,
    index_daily: pd.DataFrame,
    board_rule: BoardRule,
    lookahead_days: int = 10,
    history_days: int = 90,
) -> dict:
    if stock_daily.empty or index_daily.empty:
        raise ValueError("个股或基准指数数据为空")
    if "close" not in stock_daily.columns or "close" not in index_daily.columns:
        raise ValueError("缺少收盘价数据，无法计算异动")

    stock = stock_daily.copy().sort_index()
    index = index_daily.copy().sort_index()
    stock["close"] = pd.to_numeric(stock["close"], errors="coerce")
    index["close"] = pd.to_numeric(index["close"], errors="coerce")
    stock["stock_pct"] = _pct_change(stock)
    index["index_pct"] = _pct_change(index)

    if "turnover" in stock.columns:
        stock["turnover"] = pd.to_numeric(stock["turnover"], errors="coerce")
    else:
        stock["turnover"] = float("nan")

    df = stock[["close", "stock_pct", "turnover"]].join(
        index[["close", "index_pct"]].rename(columns={"close": "index_close"}),
        how="inner",
    )
    df = df.dropna(subset=["close", "stock_pct", "index_pct"])
    if len(df) < 31:
        raise ValueError("有效交易日不足，至少需要 31 个交易日")

    df["deviation"] = df["stock_pct"] - df["index_pct"]
    df["dev_3d"] = _window_deviation(df["close"], df["index_close"], 3)
    df["dev_10d"] = _window_deviation(df["close"], df["index_close"], 10)
    df["dev_30d"] = _window_deviation(df["close"], df["index_close"], 30)
    df["turnover_3d"] = df["turnover"].rolling(3).sum()
    df["turnover_3d_avg"] = df["turnover"].rolling(3).mean()
    df["turnover_prev5_avg"] = df["turnover"].shift(3).rolling(5).mean()
    df["turnover_ratio"] = df["turnover_3d_avg"] / df["turnover_prev5_avg"]

    rows = []
    ordinary_events = []
    start_index = max(30, len(df) - history_days)
    for position, (date, row) in enumerate(df.iterrows()):
        price_direction = _direction(row["dev_3d"], board_rule.ordinary_up, board_rule.ordinary_down)
        turnover_trigger = bool(
            board_rule.has_turnover_rule
            and pd.notna(row["turnover_ratio"])
            and pd.notna(row["turnover_3d"])
            and row["turnover_ratio"] >= 30
            and row["turnover_3d"] >= 20
        )
        ordinary_trigger = bool(price_direction is not None or turnover_trigger)

        if ordinary_trigger:
            ordinary_events.append({
                "date": date,
                "direction": price_direction or "turnover",
                "reason": "价格偏离" if price_direction else "换手率异常",
            })

        severe_10_up = bool(row["dev_10d"] >= 100) if pd.notna(row["dev_10d"]) else False
        severe_10_down = bool(row["dev_10d"] <= -50) if pd.notna(row["dev_10d"]) else False
        severe_30_up = bool(row["dev_30d"] >= 200) if pd.notna(row["dev_30d"]) else False
        severe_30_down = bool(row["dev_30d"] <= -70) if pd.notna(row["dev_30d"]) else False

        recent_start = df.index[max(0, position - 9)]
        recent_10_events = [
            event for event in ordinary_events
            if event["date"] >= recent_start and event["date"] <= date
        ]
        up_events = [event for event in recent_10_events if event["direction"] == "up"]
        down_events = [event for event in recent_10_events if event["direction"] == "down"]
        same_direction_trigger = (
            len(up_events) >= board_rule.same_direction_count
            or len(down_events) >= board_rule.same_direction_count
        )

        severe_reasons = []
        if same_direction_trigger:
            severe_reasons.append(f"10 日内 {board_rule.same_direction_count} 次同向普通异动")
        if severe_10_up or severe_10_down:
            severe_reasons.append("10 日极端偏离")
        if severe_30_up or severe_30_down:
            severe_reasons.append("30 日极端偏离")

        if position >= start_index:
            prev_close = float(df["close"].iloc[position - 1]) if position > 0 else None

            def current_target(window: int, target: float):
                base_idx = position - window
                if base_idx < 0:
                    return None, None, None, None
                target_price = _target_price_for_window(
                    float(df["close"].iloc[base_idx]),
                    float(df["index_close"].iloc[base_idx]),
                    float(row["index_close"]),
                    target,
                )
                daily_pct = (target_price / prev_close - 1) * 100 if prev_close else None
                gap_pct = (target_price / float(row["close"]) - 1) * 100 if row["close"] else None
                return target_price, daily_pct, gap_pct, df.index[base_idx]

            severe_30_price, severe_30_daily_pct, severe_30_gap_pct, severe_30_base_date = current_target(30, 200)
            severe_10_price, severe_10_daily_pct, severe_10_gap_pct, severe_10_base_date = current_target(10, 100)
            ordinary_up_price, ordinary_up_daily_pct, ordinary_up_gap_pct, ordinary_base_date = current_target(3, board_rule.ordinary_up)
            rows.append({
                "date": date.strftime("%Y-%m-%d"),
                "type": "history",
                "close": _round(row["close"]),
                "stock_pct": _round(row["stock_pct"]),
                "index_pct": _round(row["index_pct"]),
                "deviation": _round(row["deviation"]),
                "dev_3d": _round(row["dev_3d"]),
                "dev_10d": _round(row["dev_10d"]),
                "dev_30d": _round(row["dev_30d"]),
                "turnover_3d": _round(row["turnover_3d"]),
                "turnover_ratio": _round(row["turnover_ratio"]),
                "ordinary_trigger": ordinary_trigger,
                "ordinary_direction": price_direction,
                "ordinary_reason": "价格偏离" if price_direction else ("换手率异常" if turnover_trigger else None),
                "severe_trigger": bool(severe_reasons),
                "severe_reasons": severe_reasons,
                "ordinary_up_price": _round(ordinary_up_price),
                "ordinary_up_daily_pct": _round(ordinary_up_daily_pct),
                "ordinary_up_gap_pct": _round(ordinary_up_gap_pct),
                "ordinary_base_date": ordinary_base_date.strftime("%Y-%m-%d") if ordinary_base_date is not None else None,
                "severe_10_up_price": _round(severe_10_price),
                "severe_10_up_daily_pct": _round(severe_10_daily_pct),
                "severe_10_up_gap_pct": _round(severe_10_gap_pct),
                "severe_10_base_date": severe_10_base_date.strftime("%Y-%m-%d") if severe_10_base_date is not None else None,
                "severe_30_up_price": _round(severe_30_price),
                "severe_30_up_daily_pct": _round(severe_30_daily_pct),
                "severe_30_up_gap_pct": _round(severe_30_gap_pct),
                "severe_30_base_date": severe_30_base_date.strftime("%Y-%m-%d") if severe_30_base_date is not None else None,
            })

    latest = rows[-1]
    last_close = float(df["close"].iloc[-1])
    latest_index_pct = float(df["index_pct"].tail(5).mean())
    last_index_close = float(df["index_close"].iloc[-1])
    future_dates = next_business_days(df.index[-1], lookahead_days)
    future_rows = []

    future_index_pct = latest_index_pct if pd.notna(latest_index_pct) else 0

    for future_offset, date in enumerate(future_dates):
        days_ahead = future_offset + 1
        future_index_close = last_index_close * ((1 + future_index_pct / 100) ** days_ahead)

        def future_target(window: int, target: float):
            base_idx = len(df) + future_offset - window
            if base_idx < 0 or base_idx >= len(df):
                return None, None, None, None
            stock_base = float(df["close"].iloc[base_idx])
            index_base = float(df["index_close"].iloc[base_idx])
            target_price = _target_price_for_window(stock_base, index_base, future_index_close, target)
            target_pct = (target_price / last_close - 1) * 100
            return target_price, target_pct, stock_base, df.index[base_idx]

        ordinary_up_price, ordinary_up_pct, ordinary_base, ordinary_base_date = future_target(3, board_rule.ordinary_up)
        ordinary_down_price, ordinary_down_pct, _, _ = future_target(3, board_rule.ordinary_down)
        severe_10_up_price, severe_10_up_pct, severe_10_base, severe_10_base_date = future_target(10, 100)
        severe_30_up_price, severe_30_up_pct, severe_30_base, severe_30_base_date = future_target(30, 200)

        future_rows.append({
            "date": date.strftime("%Y-%m-%d"),
            "type": "future",
            "close": None,
            "stock_pct": None,
            "index_pct": _round(future_index_pct),
            "deviation": None,
            "dev_3d": None,
            "dev_10d": None,
            "dev_30d": None,
            "ordinary_up_price": _round(ordinary_up_price),
            "ordinary_down_price": _round(ordinary_down_price),
            "severe_10_up_price": _round(severe_10_up_price),
            "severe_30_up_price": _round(severe_30_up_price),
            "ordinary_up_pct": _round(ordinary_up_pct),
            "ordinary_down_pct": _round(ordinary_down_pct),
            "severe_10_up_pct": _round(severe_10_up_pct),
            "severe_30_up_pct": _round(severe_30_up_pct),
            "ordinary_base_close": _round(ordinary_base),
            "ordinary_base_date": ordinary_base_date.strftime("%Y-%m-%d") if ordinary_base_date is not None else None,
            "severe_10_base_close": _round(severe_10_base),
            "severe_10_base_date": severe_10_base_date.strftime("%Y-%m-%d") if severe_10_base_date is not None else None,
            "severe_30_base_close": _round(severe_30_base),
            "severe_30_base_date": severe_30_base_date.strftime("%Y-%m-%d") if severe_30_base_date is not None else None,
        })

    latest_events = ordinary_events[-8:]
    return {
        "board": {
            "key": board_rule.board,
            "name": board_rule.board_name,
            "is_st": board_rule.is_st,
            "ordinary_up": board_rule.ordinary_up,
            "ordinary_down": board_rule.ordinary_down,
            "same_direction_count": board_rule.same_direction_count,
            "has_turnover_rule": board_rule.has_turnover_rule,
        },
        "benchmark": {
            "symbol": board_rule.index_symbol,
            "name": board_rule.index_name,
        },
        "latest": latest,
        "events": [
            {
                "date": event["date"].strftime("%Y-%m-%d"),
                "direction": event["direction"],
                "reason": event["reason"],
            }
            for event in latest_events
        ],
        "history": rows,
        "future": future_rows,
        "chart": rows + future_rows,
        "notes": [
            "新股前 5 个交易日、全天停牌或无成交日不纳入统计；当前按可取得交易日数据近似处理。",
            "公告重置、复牌清零、监管期清零需要人工确认公告日期；本计算默认按连续交易日滚动监控。",
            "未来触线价格按区间累计涨幅偏离反推，并使用最近 5 个交易日基准指数平均涨跌幅作估算，不代表预测。",
        ],
    }
