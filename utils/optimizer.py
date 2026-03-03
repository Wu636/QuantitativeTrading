"""
参数优化器 - 网格搜索最优参数组合

使用方式：
    optimizer = StrategyOptimizer(data, StrategyClass)
    best_params, results = optimizer.optimize(param_grid)
"""

import pandas as pd
import numpy as np
from itertools import product
from backtest.engine import BacktestEngine, BacktestConfig
from utils.metrics import calc_metrics
import warnings

warnings.filterwarnings("ignore")


class StrategyOptimizer:
    """策略参数优化器"""

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
            行情数据
        strategy_class : type
            策略类（注意是类本身，不是实例）
        config : BacktestConfig
            回测配置
        """
        self.data = data
        self.strategy_class = strategy_class
        self.config = config or BacktestConfig()

    def optimize(
        self,
        param_grid: dict,
        sort_by: str = "sharpe_ratio",
        top_n: int = 10,
        verbose: bool = True,
    ) -> tuple[dict, pd.DataFrame]:
        """
        网格搜索最优参数

        Parameters
        ----------
        param_grid : dict
            参数搜索空间，如:
            {
                "short_window": [5, 10, 15],
                "long_window": [20, 30, 60],
            }
        sort_by : str
            排序指标，可选: "total_return", "sharpe_ratio", "max_drawdown", "win_rate"
        top_n : int
            返回前N个最优结果
        verbose : bool
            是否打印进度

        Returns
        -------
        tuple[dict, pd.DataFrame]
            (最优参数, 所有结果DataFrame)
        """
        param_names = list(param_grid.keys())
        param_values = list(param_grid.values())
        all_combinations = list(product(*param_values))

        total = len(all_combinations)
        if verbose:
            print(f"\n🔍 开始参数优化: {self.strategy_class.name if hasattr(self.strategy_class, 'name') else self.strategy_class.__name__}")
            print(f"  参数空间: {param_names}")
            print(f"  总组合数: {total}")
            print("-" * 60)

        results = []

        for idx, combo in enumerate(all_combinations):
            params = dict(zip(param_names, combo))

            # 跳过无效参数（如短期 >= 长期）
            if "short_window" in params and "long_window" in params:
                if params["short_window"] >= params["long_window"]:
                    continue
            if "fast_ma" in params and "slow_ma" in params:
                if params["fast_ma"] >= params["slow_ma"]:
                    continue

            try:
                # 静默运行
                import io, sys
                old_stdout = sys.stdout
                sys.stdout = io.StringIO()

                strategy = self.strategy_class(**params)
                signals = strategy.generate_signals(self.data)
                engine = BacktestEngine(self.config)
                bt_result = engine.run(self.data, signals)
                metrics = calc_metrics(bt_result)

                sys.stdout = old_stdout

                row = {**params, **{
                    "total_return": metrics["total_return"],
                    "annual_return": metrics["annual_return"],
                    "max_drawdown": metrics["max_drawdown"],
                    "sharpe_ratio": metrics["sharpe_ratio"],
                    "win_rate": metrics["win_rate"],
                    "total_trades": metrics["total_trades"],
                    "profit_loss_ratio": metrics["profit_loss_ratio"],
                }}
                results.append(row)

            except Exception as e:
                import sys as _sys
                if _sys.stdout != old_stdout:
                    _sys.stdout = old_stdout
                if verbose:
                    print(f"  ⚠️ 参数 {params} 运行失败: {e}")
                continue

            if verbose and (idx + 1) % max(1, total // 10) == 0:
                print(f"  进度: {idx + 1}/{total} ({(idx + 1) / total:.0%})")

        if not results:
            print("❌ 没有有效的优化结果")
            return {}, pd.DataFrame()

        results_df = pd.DataFrame(results)

        # 排序
        ascending = sort_by == "max_drawdown"  # 回撤越小越好
        results_df = results_df.sort_values(sort_by, ascending=ascending).reset_index(drop=True)

        best_params = {k: results_df.iloc[0][k] for k in param_names}

        if verbose:
            print(f"\n{'=' * 60}")
            print(f"  🏆 优化完成！按 {sort_by} 排序的 Top {min(top_n, len(results_df))} 参数组合:")
            print(f"{'=' * 60}")
            display_cols = param_names + ["total_return", "annual_return", "max_drawdown", "sharpe_ratio", "win_rate", "total_trades"]
            print(results_df[display_cols].head(top_n).to_string(
                float_format=lambda x: f"{x:.4f}" if abs(x) < 10 else f"{x:.2f}",
                index=True,
            ))
            print(f"\n  ✅ 最优参数: {best_params}")
            print(f"  总收益: {results_df.iloc[0]['total_return']:.2%}, "
                  f"夏普: {results_df.iloc[0]['sharpe_ratio']:.2f}, "
                  f"最大回撤: {results_df.iloc[0]['max_drawdown']:.2%}")

        return best_params, results_df
