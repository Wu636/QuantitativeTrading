"""
多因子打分模型

对经过筛选的股票按多个因子打分排序。
使用排名百分位法（rank percentile），每个因子得到 0~100 的分数，
然后按权重加权得到综合得分。

支持的因子：
1. 价值因子（EP = 1/PE，越高越便宜）
2. 动量因子（60日涨幅，越高动量越强）
3. 质量因子（近似用 1/PB 反映 ROE 水平）
4. 流动性因子（换手率，适中为佳）
5. 市值因子（小市值因子，市值越小分越高）
"""

import pandas as pd
import numpy as np


class FactorScorer:
    """多因子打分器"""

    # 默认因子权重（7 因子，后 2 个默认关闭，旧模板兼容）
    DEFAULT_WEIGHTS = {
        "value": 0.25,          # 价值因子（EP = 1/PE）
        "momentum": 0.25,       # 动量因子（60日涨幅）
        "quality": 0.20,        # 质量因子（1/PB）
        "liquidity": 0.10,      # 流动性因子（换手率）
        "size": 0.20,           # 市值因子（小市值溢价）
        "capital_flow": 0.0,    # 资金流因子（主力净流入 / 量比代理）
        "roe": 0.0,             # ROE 因子（PB/PE 近似）
    }

    def __init__(self, weights: dict = None):
        """
        Parameters
        ----------
        weights : dict
            因子权重字典，键为因子名，值为权重。
            权重会自动归一化。
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        # 归一化
        total = sum(self.weights.values())
        if total > 0:
            self.weights = {k: v / total for k, v in self.weights.items()}

    def score(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        对股票池进行多因子打分

        Parameters
        ----------
        df : pd.DataFrame
            经过筛选的股票 DataFrame（来自 akshare 全市场快照）

        Returns
        -------
        pd.DataFrame
            新增 factor_* 和 total_score 列的 DataFrame，按 total_score 降序
        """
        result = df.copy()

        # ===== 计算各因子得分（用排名百分位，0~100 分）=====

        # 1. 价值因子：EP = 1/PE（PE 越低，EP 越高，分越高）
        if "市盈率-动态" in result.columns:
            pe = result["市盈率-动态"].replace(0, np.nan)
            ep = 1.0 / pe
            result["factor_value"] = ep.rank(pct=True, na_option="bottom") * 100
        else:
            result["factor_value"] = 50.0

        # 2. 动量因子：60 日涨幅排名（涨幅越大分越高）
        if "60日涨跌幅" in result.columns:
            result["factor_momentum"] = (
                result["60日涨跌幅"].rank(pct=True, na_option="bottom") * 100
            )
        else:
            result["factor_momentum"] = 50.0

        # 3. 质量因子：1/PB 近似 ROE（PB 越低、ROE 相对越高）
        if "市净率" in result.columns:
            pb = result["市净率"].replace(0, np.nan)
            inv_pb = 1.0 / pb
            result["factor_quality"] = inv_pb.rank(pct=True, na_option="bottom") * 100
        else:
            result["factor_quality"] = 50.0

        # 4. 流动性因子：换手率适中最优（2~5%为佳）
        if "换手率" in result.columns:
            # 离理想换手率 3% 越近分越高
            ideal_turnover = 3.0
            deviation = (result["换手率"] - ideal_turnover).abs()
            result["factor_liquidity"] = (
                (1 - deviation.rank(pct=True, na_option="bottom")) * 100
            )
        else:
            result["factor_liquidity"] = 50.0

        # 5. 市值因子：小市值溢价（市值越小分越高）
        if "总市值" in result.columns:
            result["factor_size"] = (
                (1 - result["总市值"].rank(pct=True, na_option="bottom")) * 100
            )
        else:
            result["factor_size"] = 50.0

        # 6. 资金流因子：主力净流入排名（数据来自资金流接口 / 量比代理）
        if "主力净流入占比" in result.columns:
            # 有真实资金流数据，直接排名
            result["factor_capital_flow"] = (
                result["主力净流入占比"].rank(pct=True, na_option="bottom") * 100
            )
        elif "量比" in result.columns:
            # 无资金流数据时，用量比作为资金关注度的代理指标
            result["factor_capital_flow"] = (
                result["量比"].rank(pct=True, na_option="bottom") * 100
            )
        else:
            result["factor_capital_flow"] = 50.0

        # 7. ROE 因子：ROE ≈ PB / PE × 100（从估值指标逆推盈利能力）
        if "市净率" in result.columns and "市盈率-动态" in result.columns:
            pe = result["市盈率-动态"].replace(0, np.nan)
            roe_approx = (result["市净率"] / pe).clip(lower=0)  # 排除亏损股
            result["factor_roe"] = roe_approx.rank(pct=True, na_option="bottom") * 100
        else:
            result["factor_roe"] = 50.0

        # ===== 加权综合得分 =====
        factor_map = {
            "value": "factor_value",
            "momentum": "factor_momentum",
            "quality": "factor_quality",
            "liquidity": "factor_liquidity",
            "size": "factor_size",
            "capital_flow": "factor_capital_flow",
            "roe": "factor_roe",
        }

        result["total_score"] = 0.0
        for factor_name, col_name in factor_map.items():
            weight = self.weights.get(factor_name, 0)
            result["total_score"] += result[col_name] * weight

        result["total_score"] = result["total_score"].round(2)

        # 按综合得分降序排列
        result = result.sort_values("total_score", ascending=False).reset_index(drop=True)

        return result
