"""
可视化模块 - 生成回测报告图表

包含：
1. K线图 + 均线 + 买卖信号
2. 成交量图
3. 策略净值 vs 基准净值
4. 回撤曲线
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.patches import FancyArrowPatch
import os

# 配置中文字体
plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "SimHei", "Heiti TC", "PingFang SC"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["figure.dpi"] = 120
plt.rcParams["figure.facecolor"] = "white"


def plot_backtest_report(
    data: pd.DataFrame,
    signals: pd.DataFrame,
    result: dict,
    metrics: dict,
    strategy_name: str = "",
    stock_name: str = "",
    save_path: str = None,
):
    """
    生成完整的回测可视化报告

    Parameters
    ----------
    data : pd.DataFrame
        原始行情数据
    signals : pd.DataFrame
        策略信号（包含 signal, short_ma, long_ma）
    result : dict
        回测引擎返回结果
    metrics : dict
        绩效指标
    strategy_name : str
        策略名称
    stock_name : str
        股票名称
    save_path : str
        图片保存路径，None则直接显示
    """
    daily_df = result["daily_df"]
    trades = result["trades"]

    # 合并数据用于绘图
    plot_data = data.copy()
    # 只保留回测区间内的数据
    common_idx = plot_data.index.intersection(signals.index)
    plot_data = plot_data.loc[common_idx]
    sig_data = signals.loc[common_idx]

    fig = plt.figure(figsize=(16, 20))
    title = f"{stock_name} - {strategy_name} 回测报告" if stock_name else f"{strategy_name} 回测报告"
    fig.suptitle(title, fontsize=16, fontweight="bold", y=0.98)

    # ========== 子图1: K线图 + 均线 + 买卖信号 ==========
    ax1 = fig.add_subplot(4, 1, 1)

    # 画收盘价
    ax1.plot(plot_data.index, plot_data["close"], color="#333333", linewidth=1.0, label="收盘价", alpha=0.8)

    # 画均线
    if "short_ma" in sig_data.columns:
        ax1.plot(sig_data.index, sig_data["short_ma"], color="#FF6B6B", linewidth=1.0,
                 label=f"MA{result.get('short_window', 5)}", alpha=0.9)
    if "long_ma" in sig_data.columns:
        ax1.plot(sig_data.index, sig_data["long_ma"], color="#4ECDC4", linewidth=1.0,
                 label=f"MA{result.get('long_window', 20)}", alpha=0.9)

    # 标记买卖点
    buy_signals = sig_data[sig_data["signal"] == 1]
    sell_signals = sig_data[sig_data["signal"] == -1]

    # 只标记实际成交的买卖点
    buy_dates = [t.date for t in trades if t.action == "buy"]
    sell_dates = [t.date for t in trades if t.action == "sell"]

    for d in buy_dates:
        if d in plot_data.index:
            ax1.scatter(d, plot_data.loc[d, "close"], marker="^", color="#FF4444",
                       s=120, zorder=5, edgecolors="black", linewidths=0.5)
    for d in sell_dates:
        if d in plot_data.index:
            ax1.scatter(d, plot_data.loc[d, "close"], marker="v", color="#00CC66",
                       s=120, zorder=5, edgecolors="black", linewidths=0.5)

    # 在图例中添加买卖标记说明
    ax1.scatter([], [], marker="^", color="#FF4444", s=80, label="买入", edgecolors="black", linewidths=0.5)
    ax1.scatter([], [], marker="v", color="#00CC66", s=80, label="卖出", edgecolors="black", linewidths=0.5)

    ax1.set_title("价格走势 & 交易信号", fontsize=13, fontweight="bold")
    ax1.set_ylabel("价格 (元)")
    ax1.legend(loc="upper left", fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    # ========== 子图2: 成交量 ==========
    ax2 = fig.add_subplot(4, 1, 2)

    # 根据涨跌着色
    colors = []
    for i in range(len(plot_data)):
        if i == 0:
            colors.append("#FF4444")
        elif plot_data["close"].iloc[i] >= plot_data["close"].iloc[i - 1]:
            colors.append("#FF4444")  # 红色（上涨）
        else:
            colors.append("#00CC66")  # 绿色（下跌）

    ax2.bar(plot_data.index, plot_data["volume"] / 10000, color=colors, alpha=0.7, width=1.5)
    ax2.set_title("成交量", fontsize=13, fontweight="bold")
    ax2.set_ylabel("成交量 (万手)")
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax2.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    # ========== 子图3: 净值曲线 ==========
    ax3 = fig.add_subplot(4, 1, 3)

    ax3.plot(daily_df.index, daily_df["net_value"], color="#FF6B6B", linewidth=1.5,
             label=f"策略净值 ({metrics['total_return']:.2%})")
    ax3.plot(daily_df.index, daily_df["benchmark"], color="#4ECDC4", linewidth=1.5,
             label=f"基准净值 ({metrics['benchmark_return']:.2%})", linestyle="--")

    ax3.axhline(y=1.0, color="gray", linestyle=":", alpha=0.5)
    ax3.fill_between(daily_df.index, daily_df["net_value"], 1,
                     where=daily_df["net_value"] >= 1, alpha=0.1, color="#FF6B6B")
    ax3.fill_between(daily_df.index, daily_df["net_value"], 1,
                     where=daily_df["net_value"] < 1, alpha=0.1, color="#4444FF")

    ax3.set_title("策略净值 vs 基准", fontsize=13, fontweight="bold")
    ax3.set_ylabel("净值")
    ax3.legend(loc="upper left", fontsize=10)
    ax3.grid(True, alpha=0.3)
    ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax3.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    # ========== 子图4: 回撤曲线 ==========
    ax4 = fig.add_subplot(4, 1, 4)

    cummax = daily_df["total_value"].cummax()
    drawdown = (daily_df["total_value"] - cummax) / cummax

    ax4.fill_between(drawdown.index, drawdown.values, 0, color="#FF6B6B", alpha=0.4)
    ax4.plot(drawdown.index, drawdown.values, color="#FF4444", linewidth=0.8)

    # 标记最大回撤
    max_dd_idx = drawdown.idxmin()
    ax4.scatter(max_dd_idx, drawdown[max_dd_idx], color="red", s=80, zorder=5, marker="v")
    ax4.annotate(
        f"最大回撤: {metrics['max_drawdown']:.2%}",
        xy=(max_dd_idx, drawdown[max_dd_idx]),
        xytext=(30, -20),
        textcoords="offset points",
        fontsize=9,
        color="red",
        arrowprops=dict(arrowstyle="->", color="red"),
    )

    ax4.set_title("回撤曲线", fontsize=13, fontweight="bold")
    ax4.set_ylabel("回撤幅度")
    ax4.set_xlabel("日期")
    ax4.grid(True, alpha=0.3)
    ax4.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax4.xaxis.set_major_locator(mdates.MonthLocator(interval=2))

    # ========== 添加指标文本框 ==========
    textstr = (
        f"总收益: {metrics['total_return']:.2%}  |  "
        f"年化: {metrics['annual_return']:.2%}  |  "
        f"最大回撤: {metrics['max_drawdown']:.2%}  |  "
        f"夏普: {metrics['sharpe_ratio']:.2f}  |  "
        f"胜率: {metrics['win_rate']:.2%}  |  "
        f"交易: {metrics['total_trades']}次"
    )
    fig.text(0.5, 0.01, textstr, ha="center", fontsize=10,
             bbox=dict(boxstyle="round,pad=0.5", facecolor="#F0F0F0", alpha=0.8))

    plt.tight_layout(rect=[0, 0.03, 1, 0.96])

    if save_path:
        os.makedirs(os.path.dirname(save_path) if os.path.dirname(save_path) else ".", exist_ok=True)
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"\n📊 报告图表已保存至: {save_path}")

    plt.show()
    plt.close()


def plot_trade_distribution(metrics: dict, save_path: str = None):
    """
    绘制交易盈亏分布图

    Parameters
    ----------
    metrics : dict
        calc_metrics() 返回的指标
    """
    trade_profits = metrics.get("trade_profits", [])
    if not trade_profits:
        print("没有交易记录，无法绘制分布图")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # 盈亏分布直方图
    profits = np.array(trade_profits)
    colors = ["#FF4444" if p < 0 else "#00CC66" for p in profits]

    ax1.bar(range(len(profits)), profits, color=colors, alpha=0.8)
    ax1.axhline(y=0, color="black", linewidth=0.8)
    ax1.set_title("逐笔交易盈亏", fontsize=13, fontweight="bold")
    ax1.set_xlabel("第N笔交易")
    ax1.set_ylabel("盈亏金额 (元)")
    ax1.grid(True, alpha=0.3, axis="y")

    # 累计盈亏曲线
    cum_profits = np.cumsum(profits)
    ax2.plot(range(len(cum_profits)), cum_profits, color="#FF6B6B", linewidth=2, marker="o", markersize=4)
    ax2.fill_between(range(len(cum_profits)), cum_profits, 0,
                     where=cum_profits >= 0, alpha=0.2, color="#00CC66")
    ax2.fill_between(range(len(cum_profits)), cum_profits, 0,
                     where=cum_profits < 0, alpha=0.2, color="#FF4444")
    ax2.axhline(y=0, color="black", linewidth=0.8)
    ax2.set_title("累计盈亏", fontsize=13, fontweight="bold")
    ax2.set_xlabel("第N笔交易")
    ax2.set_ylabel("累计盈亏 (元)")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        print(f"📊 交易分布图已保存至: {save_path}")

    plt.show()
    plt.close()
