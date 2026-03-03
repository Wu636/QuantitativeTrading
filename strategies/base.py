"""
策略基类 - 所有策略都应继承此类

如何添加新策略：
1. 在 strategies/ 目录下创建新文件，如 my_strategy.py
2. 继承 StrategyBase 类
3. 实现 generate_signals() 方法
4. （可选）重写 name 属性和 description

示例：
    class MyStrategy(StrategyBase):
        name = "我的策略"

        def generate_signals(self, data):
            signals = pd.DataFrame(index=data.index)
            signals["signal"] = 0
            # ... 你的策略逻辑 ...
            return signals
"""

from abc import ABC, abstractmethod
import pandas as pd


class StrategyBase(ABC):
    """策略基类"""

    name: str = "BaseStrategy"
    description: str = "策略基类"

    def __init__(self, **params):
        """
        初始化策略参数

        Parameters
        ----------
        **params
            策略参数，子类自定义
        """
        self.params = params

    @abstractmethod
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        根据行情数据生成交易信号

        Parameters
        ----------
        data : pd.DataFrame
            行情数据（已包含所需的技术指标）

        Returns
        -------
        pd.DataFrame
            信号DataFrame，必须包含 signal 列：
            - 1: 买入信号
            - -1: 卖出信号
            - 0: 无操作
        """
        raise NotImplementedError

    def __repr__(self):
        params_str = ", ".join(f"{k}={v}" for k, v in self.params.items())
        return f"{self.name}({params_str})"
