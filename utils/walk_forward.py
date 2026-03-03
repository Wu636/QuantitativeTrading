"""
Walk-Forward 分析（前推优化）— 防过拟合参数优化工具

原理：
1. 将历史数据切分为多个滚动窗口：[训练集 | 测试集]
2. 在每个训练集上用网格搜索找到最优参数
3. 在对应测试集上用该参数进行样本外验证
4. 汇总所有测试集结果，计算"样本外"真实表现

优势：
- 避免全样本优化导致的过拟合
- 模拟真实交易中"先用历史调参，再用于未来"的过程
- 过拟合比率 > 2 说明严重过拟合

使用方式：
    analyzer = WalkForwardAnalyzer(data, DualMAStrategy, config)
    summary, details = analyzer.run(param_grid, train_days=252, test_days=126)
"""

import pandas as pd
import numpy as np
from backtest.engine import BacktestEngine, BacktestConfig
from utils.metrics import calc_metrics
from utils.optimizer import StrategyOptimizer
import warnings
import io
import sys

warnings.filterwarnings("ignore")


class WalkForwardAnalyzer:
    """Walk-Forward 前推优化分析器"""

    def __init__(
        self,
        data: pd.DataFrame,
        strategy_class: type,
        config: BacktestConfig = None,
    ):
        """
        Parameters
        ----------
        data : pd.DataFrame
            完整的行情数据（越长越好，建议 3 年以上）
        strategy_class : type
            策略类（不是实例）
        config : BacktestConfig
            回测配置
        """
        self.data = data
        self.strategy_class = strategy_class
        self.config = config or BacktestConfig()

    def _split_windows(
        self,
        train_days: int = 252,
        test_days: int = 126,
        step_days: int = None,
    ) -> list[tuple[pd.DataFrame, pd.DataFrame]]:
        """
        将数据切分为滚动的 (train, test) 窗口对

        Parameters
        ----------
        train_days : int
            训练集交易日数（默认 252，约 1 年）
        test_days : int
            测试集交易日数（默认 126，约 6 个月）
        step_days : int
            窗口步进天数（默认 = test_days）

        Returns
        -------
        list[tuple[DataFrame, DataFrame]]
            [(train_1, test_1), (train_2, test_2), ...]
        """
        if step_days is None:
            step_days = test_days

        total = len(self.data)
        windows = []
        start = 0

        while start + train_days + test_days <= total:
            train = self.data.iloc[start: start + train_days]
            test = self.data.iloc[start + train_days: start + train_days + test_days]
            windows.append((train, test))
            start += step_days

        return windows

    def run(
        self,
        param_grid: dict,
        train_days: int = 252,
        test_days: int = 126,
        step_days: int = None,
        optimize_by: str = "sharpe_ratio",
    ) -> tuple[dict, pd.DataFrame]:
        """
        运行 Walk-Forward 分析

        Parameters
        ----------
        param_grid : dict
            参数搜索空间（同 StrategyOptimizer）
        train_days : int
            训练集天数
        test_days : int
            测试集天数
        step_days : int
            步进天数
        optimize_by : str
            优化目标指标

        Returns
        -------
        tuple[dict, pd.DataFrame]
            (汇总统计, 各窗口详细结果)
        """
        strategy_name = (
            self.strategy_class.name
            if hasattr(self.strategy_class, "name")
            else self.strategy_class.__name__
        )

        print("=" * 70)
        print(f"  🔄 Walk-Forward 分析 — {strategy_name}")
        print("=" * 70)

        windows = self._split_windows(train_days, test_days, step_days)

        if len(windows) < 2:
            print("⚠️ 数据不足，无法创建足够的滚动窗口。请使用更长的数据或缩短窗口。")
            return {}, pd.DataFrame()

        print(f"  数据总量: {len(self.data)} 交易日")
        print(f"  训练窗口: {train_days} 天, 测试窗口: {test_days} 天")
        print(f"  滚动窗口数: {len(windows)}")
        print("-" * 70)

        details = []

        for i, (train_data, test_data) in enumerate(windows):
            train_start = train_data.index[0].strftime("%Y-%m-%d")
            train_end = train_data.index[-1].strftime("%Y-%m-%d")
            test_start = test_data.index[0].strftime("%Y-%m-%d")
            test_end = test_data.index[-1].strftime("%Y-%m-%d")

            print(f"\n  📋 窗口 {i + 1}/{len(windows)}")
            print(f"     训练: {train_start} ~ {train_end} ({len(train_data)} 天)")
            print(f"     测试: {test_start} ~ {test_end} ({len(test_data)} 天)")

            # --- 训练阶段：在训练集上优化参数 ---
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()

            try:
                optimizer = StrategyOptimizer(train_data, self.strategy_class, self.config)
                best_params, _ = optimizer.optimize(
                    param_grid,
                    sort_by=optimize_by,
                    top_n=1,
                    verbose=False,
                )
            except Exception as e:
                sys.stdout = old_stdout
                print(f"     ❌ 训练阶段失败: {e}")
                continue

            sys.stdout = old_stdout

            if not best_params:
                print("     ❌ 未找到有效参数")
                continue

            print(f"     最优参数: {best_params}")

            # --- 训练集上的表现（样本内） ---
            try:
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                strategy_in = self.strategy_class(**best_params)
                signals_in = strategy_in.generate_signals(train_data)
                engine_in = BacktestEngine(self.config)
                result_in = engine_in.run(train_data, signals_in)
                metrics_in = calc_metrics(result_in)

                sys.stdout = old_stdout
            except Exception as e:
                sys.stdout = old_stdout
                metrics_in = {"sharpe_ratio": 0, "total_return": 0, "max_drawdown": 0}

            # --- 测试阶段：在测试集上验证 ---
            try:
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                strategy_out = self.strategy_class(**best_params)
                signals_out = strategy_out.generate_signals(test_data)
                engine_out = BacktestEngine(self.config)
                result_out = engine_out.run(test_data, signals_out)
                metrics_out = calc_metrics(result_out)

                sys.stdout = old_stdout
            except Exception as e:
                sys.stdout = old_stdout
                print(f"     ❌ 测试阶段失败: {e}")
                continue

            in_sharpe = metrics_in["sharpe_ratio"]
            out_sharpe = metrics_out["sharpe_ratio"]
            in_return = metrics_in["total_return"]
            out_return = metrics_out["total_return"]

            print(f"     样本内: 收益={in_return:.2%}, 夏普={in_sharpe:.2f}")
            print(f"     样本外: 收益={out_return:.2%}, 夏普={out_sharpe:.2f}")

            details.append({
                "window": i + 1,
                "train_start": train_start,
                "train_end": train_end,
                "test_start": test_start,
                "test_end": test_end,
                "best_params": str(best_params),
                "in_sample_return": in_return,
                "in_sample_sharpe": in_sharpe,
                "in_sample_max_dd": metrics_in["max_drawdown"],
                "out_sample_return": out_return,
                "out_sample_sharpe": out_sharpe,
                "out_sample_max_dd": metrics_out["max_drawdown"],
                "out_sample_win_rate": metrics_out.get("win_rate", 0),
                "out_sample_trades": metrics_out.get("total_trades", 0),
            })

        if not details:
            print("\n❌ 所有窗口均失败")
            return {}, pd.DataFrame()

        details_df = pd.DataFrame(details)

        # ===== 汇总统计 =====
        avg_in_sharpe = details_df["in_sample_sharpe"].mean()
        avg_out_sharpe = details_df["out_sample_sharpe"].mean()
        avg_out_return = details_df["out_sample_return"].mean()
        avg_out_dd = details_df["out_sample_max_dd"].mean()

        # 过拟合比率：样本内夏普 / 样本外夏普
        if avg_out_sharpe != 0:
            overfit_ratio = avg_in_sharpe / avg_out_sharpe
        else:
            overfit_ratio = float("inf") if avg_in_sharpe > 0 else 0

        # 样本外正收益窗口占比
        positive_windows = (details_df["out_sample_return"] > 0).sum()
        window_win_rate = positive_windows / len(details_df)

        summary = {
            "total_windows": len(details_df),
            "avg_in_sample_sharpe": round(avg_in_sharpe, 3),
            "avg_out_sample_sharpe": round(avg_out_sharpe, 3),
            "avg_out_sample_return": round(avg_out_return, 4),
            "avg_out_sample_max_dd": round(avg_out_dd, 4),
            "overfit_ratio": round(overfit_ratio, 2),
            "window_win_rate": round(window_win_rate, 3),
        }

        print(f"\n\n{'=' * 70}")
        print(f"  📊 Walk-Forward 汇总报告")
        print(f"{'=' * 70}")
        print(f"  滚动窗口数:          {summary['total_windows']}")
        print(f"  平均样本内夏普:      {summary['avg_in_sample_sharpe']:.3f}")
        print(f"  平均样本外夏普:      {summary['avg_out_sample_sharpe']:.3f}")
        print(f"  平均样本外收益:      {summary['avg_out_sample_return']:.2%}")
        print(f"  平均样本外最大回撤:  {summary['avg_out_sample_max_dd']:.2%}")
        print(f"  过拟合比率:          {summary['overfit_ratio']:.2f}")
        print(f"  窗口正收益率:        {summary['window_win_rate']:.1%}")

        # 过拟合诊断
        if overfit_ratio > 3:
            print(f"\n  ⚠️  警告：过拟合比率 = {overfit_ratio:.1f}，严重过拟合！")
            print(f"     建议：减少参数空间、增大训练窗口、或使用更简单的策略")
        elif overfit_ratio > 1.5:
            print(f"\n  ⚡ 注意：过拟合比率 = {overfit_ratio:.1f}，存在一定过拟合")
        else:
            print(f"\n  ✅ 过拟合比率 = {overfit_ratio:.1f}，样本外表现稳健")

        print(f"{'=' * 70}")

        return summary, details_df
