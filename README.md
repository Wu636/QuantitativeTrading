# 🚀 A股量化交易学习项目

一个从零开始学习A股量化交易的完整项目。包含数据获取、策略编写、回测引擎、指标计算和可视化报告。

## 📁 项目结构

```
QuantitativeTrading/
├── data/                   # 数据模块
│   ├── __init__.py
│   ├── fetcher.py          # 数据获取（akshare）
│   └── processor.py        # 数据处理（均线、涨跌停标记等）
├── strategies/             # 策略模块
│   ├── __init__.py
│   ├── base.py             # 策略基类（所有策略继承它）
│   └── dual_ma.py          # 双均线策略（示例策略）
├── backtest/               # 回测引擎
│   ├── __init__.py
│   └── engine.py           # 轻量级回测引擎（支持T+1、涨跌停）
├── utils/                  # 工具模块
│   ├── __init__.py
│   ├── metrics.py          # 绩效指标计算
│   └── plotting.py         # 可视化报告
├── output/                 # 输出目录（自动生成）
├── main.py                 # 主入口 - 运行这个文件
├── requirements.txt        # 依赖包
└── README.md               # 本文件
```

## 🏃 快速开始

### 1. 安装依赖

```bash
conda activate QuantitativeTrading
pip install -r requirements.txt
```

### 2. 运行示例

```bash
python main.py
```

这会使用 **双均线策略** 对 **平安银行(000001)** 最近2年数据进行回测，并生成：
- 控制台的绩效指标报告
- `output/000001_backtest_report.png` - 完整的K线图+信号+净值+回撤
- `output/000001_trade_distribution.png` - 交易盈亏分布

### 3. 修改参数

在 `main.py` 底部修改参数：

```python
result, metrics = run_dual_ma_backtest(
    symbol="000001",          # 改成其他股票代码
    short_window=5,           # 短期均线天数
    long_window=20,           # 长期均线天数
    initial_capital=100000,   # 初始资金
)
```

## 📊 核心模块说明

### 回测引擎 (backtest/engine.py)

- **T+1规则**：买入当天不能卖出
- **涨跌停**：涨停不能买入，跌停不能卖出
- **费用模型**：佣金(万三) + 印花税(万五, 卖出收) + 滑点(0.1%)
- **资金管理**：按100股整手买入

### 双均线策略 (strategies/dual_ma.py)

| 信号 | 条件 | 操作 |
|------|------|------|
| 金叉 🔴 | 短期MA上穿长期MA | 买入 |
| 死叉 🟢 | 短期MA下穿长期MA | 卖出 |

### 绩效指标 (utils/metrics.py)

| 指标 | 说明 |
|------|------|
| 总收益率 | (最终资产 - 初始资金) / 初始资金 |
| 年化收益率 | 按252个交易日折算 |
| 最大回撤 | 从峰值到谷值的最大跌幅 |
| 夏普比率 | 超额收益 / 波动率（无风险利率2.5%） |
| 胜率 | 盈利交易次数 / 总交易次数 |
| 盈亏比 | 平均盈利 / 平均亏损 |

## 🆕 如何添加新策略

### 第1步：创建策略文件

在 `strategies/` 目录下创建新文件，如 `strategies/rsi_strategy.py`：

```python
import pandas as pd
from .base import StrategyBase

class RSIStrategy(StrategyBase):
    """RSI超买超卖策略"""
    
    name = "RSI策略"
    description = "RSI低于30买入，高于70卖出"
    
    def __init__(self, period=14, oversold=30, overbought=70):
        super().__init__(period=period, oversold=oversold, overbought=overbought)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
    
    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        signals = pd.DataFrame(index=data.index)
        
        # 计算RSI
        delta = data["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(self.period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.period).mean()
        rs = gain / loss
        signals["rsi"] = 100 - (100 / (1 + rs))
        
        # 生成信号
        signals["signal"] = 0
        signals.loc[signals["rsi"] < self.oversold, "signal"] = 1    # 超卖买入
        signals.loc[signals["rsi"] > self.overbought, "signal"] = -1  # 超买卖出
        
        signals = signals.dropna()
        signals["signal"] = signals["signal"].astype(int)
        return signals
```

### 第2步：在 main.py 中使用

```python
from strategies.rsi_strategy import RSIStrategy

strategy = RSIStrategy(period=14, oversold=30, overbought=70)
signals = strategy.generate_signals(data)

engine = BacktestEngine(config)
result = engine.run(data, signals)
```

## 🧠 学习路线建议

1. **入门**：运行 `main.py`，理解双均线策略的信号逻辑
2. **改参数**：调整均线周期（如10/30, 20/60），观察效果变化
3. **换股票**：测试不同股票，理解策略的适用性
4. **新策略**：实现RSI、MACD、布林带等经典策略
5. **优化**：添加止损止盈、仓位管理、参数优化
6. **进阶**：多因子模型、机器学习选股

## ⚠️ 免责声明

本项目仅供学习和研究使用，不构成任何投资建议。股市有风险，投资需谨慎。回测结果不代表未来表现。
