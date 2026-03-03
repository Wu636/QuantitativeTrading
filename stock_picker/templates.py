"""
选股模板系统 — 内置策略模板 + 自定义模板 CRUD

模板包含筛选条件（filters）和因子权重（weights），
用户可直接选用内置模板或创建自定义模板。
"""

import json
import os
import uuid
from pathlib import Path

# 自定义模板存储路径
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "data"
TEMPLATES_FILE = TEMPLATES_DIR / "custom_templates.json"

# ────────────────────────────────────────────────
# 内置模板定义
# ────────────────────────────────────────────────

BUILTIN_TEMPLATES = [
    {
        "id": "trend_momentum",
        "name": "🚀 动量趋势",
        "description": "跟踪近期强势股，适合短线持仓 1-5 天",
        "builtin": True,
        "filters": {
            "max_pe": 60,
            "min_pe": 10,
            "max_pb": 10,
            "min_market_cap": 50,   # 亿元（前端单位）
            "max_market_cap": 500,
            "min_price": 5,
            "max_price": 200,
            "min_turnover": 2,
        },
        "weights": {
            "value": 0.10,
            "momentum": 0.35,
            "quality": 0.15,
            "liquidity": 0.25,
            "size": 0.15,
            "capital_flow": 0.0,
            "roe": 0.0,
        },
        "top_n": 20,
    },
    {
        "id": "value_reversion",
        "name": "💎 价值回归",
        "description": "低估值蓝筹股，适合中线持仓 5-20 天",
        "builtin": True,
        "filters": {
            "max_pe": 30,
            "min_pe": 5,
            "max_pb": 3,
            "min_market_cap": 100,
            "max_market_cap": None,
            "min_price": 5,
            "max_price": 500,
            "min_turnover": 0.5,
            "industry_pb_aware": True,   # 启用分行业 PB
        },
        "weights": {
            "value": 0.35,
            "momentum": 0.10,
            "quality": 0.30,
            "liquidity": 0.10,
            "size": 0.15,
            "capital_flow": 0.0,
            "roe": 0.0,
        },
        "top_n": 20,
    },
    {
        "id": "turtle_breakout",
        "name": "🐢 海龟突破 + ATR 止损",
        "description": "52 周新高突破 + ATR 波动率止损，完整海龟系统",
        "builtin": True,
        "filters": {
            "max_pe": 80,
            "min_pe": 10,
            "max_pb": 10,
            "min_market_cap": 30,
            "max_market_cap": 300,
            "min_price": 5,
            "max_price": 200,
            "min_turnover": 1,
            "min_volume_ratio": 1.0,  # 量比 > 1（放量确认突破）
        },
        "weights": {
            "value": 0.05,
            "momentum": 0.40,
            "quality": 0.05,
            "liquidity": 0.20,
            "size": 0.20,
            "capital_flow": 0.10,
            "roe": 0.0,
        },
        "top_n": 20,
    },
    # ── 新增策略 ①：动量 + 资金流入 ──
    {
        "id": "momentum_capital_flow",
        "name": "🔥 动量+资金流入",
        "description": "强势股 + 高换手/量比确认资金进场，胜率更高",
        "builtin": True,
        "filters": {
            "max_pe": 60,
            "min_pe": 5,
            "max_pb": 8,
            "min_market_cap": 80,
            "max_market_cap": 800,
            "min_price": 5,
            "max_price": 200,
            "min_turnover": 2,
            "min_volume_ratio": 1.2,   # 量比 > 1.2 确认资金涌入
        },
        "weights": {
            "value": 0.05,
            "momentum": 0.30,
            "quality": 0.10,
            "liquidity": 0.15,
            "size": 0.10,
            "capital_flow": 0.25,
            "roe": 0.05,
        },
        "top_n": 20,
    },
    # ── 新增策略 ②：困境反转（中线 1-3 月）──
    {
        "id": "turnaround",
        "name": "🔄 困境反转",
        "description": "低估值 + 业绩由亏转盈的戴维斯双击，适合中线 1-3 个月",
        "builtin": True,
        "filters": {
            "max_pe": 25,
            "min_pe": 3,       # PE 极低 → 之前亏损严重，现在刚转正
            "max_pb": 3,
            "min_market_cap": 50,
            "max_market_cap": 500,
            "min_price": 3,
            "max_price": 80,
            "min_turnover": 0.5,
            "industry_pb_aware": True,  # 银行/地产 PB < 1 正常
            "min_roe": 5,              # ROE > 5% 确认盈利转正
        },
        "weights": {
            "value": 0.30,
            "momentum": 0.05,
            "quality": 0.15,
            "liquidity": 0.05,
            "size": 0.15,
            "capital_flow": 0.0,
            "roe": 0.30,
        },
        "top_n": 20,
    },
    # ── 新增策略 ③：量价背离 + 基本面双重过滤 ──
    {
        "id": "volume_price_divergence",
        "name": "📊 量价背离精选",
        "description": "缩量横盘 + ROE>15% + PE合理 → 等待右侧放量突破",
        "builtin": True,
        "filters": {
            "max_pe": 35,
            "min_pe": 5,
            "max_pb": 6,
            "min_market_cap": 80,
            "max_market_cap": 1000,
            "min_price": 5,
            "max_price": 200,
            "min_turnover": 0.3,
            "min_roe": 15,             # ROE > 15%（优秀基本面）
            "max_volume_ratio": 0.8,   # 量比 < 0.8（缩量横盘中）
        },
        "weights": {
            "value": 0.20,
            "momentum": 0.05,
            "quality": 0.25,
            "liquidity": 0.10,
            "size": 0.10,
            "capital_flow": 0.0,
            "roe": 0.30,
        },
        "top_n": 20,
    },
]


# ────────────────────────────────────────────────
# 自定义模板 CRUD
# ────────────────────────────────────────────────

def _load_custom_templates() -> list[dict]:
    """从 JSON 文件加载自定义模板"""
    if not TEMPLATES_FILE.exists():
        return []
    try:
        with open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def _save_custom_templates(templates: list[dict]):
    """保存自定义模板到 JSON 文件"""
    TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
    with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
        json.dump(templates, f, ensure_ascii=False, indent=2)


def list_all_templates() -> list[dict]:
    """返回所有模板（内置 + 自定义）"""
    return BUILTIN_TEMPLATES + _load_custom_templates()


def get_template(template_id: str) -> dict | None:
    """根据 ID 获取模板"""
    for t in list_all_templates():
        if t["id"] == template_id:
            return t
    return None


def create_template(
    name: str,
    description: str,
    filters: dict,
    weights: dict,
    top_n: int = 20,
) -> dict:
    """创建自定义模板"""
    template = {
        "id": f"custom_{uuid.uuid4().hex[:8]}",
        "name": name,
        "description": description,
        "builtin": False,
        "filters": filters,
        "weights": weights,
        "top_n": top_n,
    }
    customs = _load_custom_templates()
    customs.append(template)
    _save_custom_templates(customs)
    return template


def delete_template(template_id: str) -> bool:
    """删除自定义模板，返回是否成功"""
    customs = _load_custom_templates()
    original_len = len(customs)
    customs = [t for t in customs if t["id"] != template_id]
    if len(customs) < original_len:
        _save_custom_templates(customs)
        return True
    return False
