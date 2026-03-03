"""
基本面分析器 — 从实时行情快照中提取估值数据

通过新浪 API 获取个股实时信息（PE/PB/市值/换手率等）；
ROE 通过 PB/PE 近似计算。
"""

import os
import json
import subprocess
import pandas as pd
import numpy as np


def _clear_proxy():
    for key in ["http_proxy", "https_proxy", "all_proxy",
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        os.environ.pop(key, None)


def _safe_float(val):
    if val is None or val == "" or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


class FundamentalAnalyzer:
    """基本面分析"""

    # 行业 PE 参考中位数（A股经验值）
    INDUSTRY_PE_REF = {
        "银行": 6,
        "保险": 10,
        "地产": 8,
        "证券": 20,
        "白酒": 30,
        "医药": 28,
        "科技": 35,
        "新能源": 40,
        "消费": 25,
    }

    def __init__(self, code: str):
        self.code = code
        self.data = self._fetch_realtime()

    def _fetch_realtime(self) -> dict:
        """从新浪财经获取个股实时数据"""
        _clear_proxy()
        # 判断 sh/sz
        prefix = "sh" if self.code.startswith(("6", "9")) else "sz"
        symbol = f"{prefix}{self.code}"

        data = {}

        # ===== hq.sinajs.cn — 基本行情 + _i 后缀带估值数据 =====
        # 一次请求同时拿行情和扩展信息
        try:
            result = subprocess.run(
                [
                    "curl", "-s", "-m", "10",
                    "--noproxy", "*",
                    "-H", "User-Agent: Mozilla/5.0",
                    "-H", "Referer: https://finance.sina.com.cn/",
                    f"https://hq.sinajs.cn/list={symbol},{symbol}_i",
                ],
                capture_output=True, timeout=12,
            )
            # 新浪返回 GBK 编码
            stdout = result.stdout.decode("gbk", errors="replace")

            lines = stdout.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                var_name = line.split("=")[0]  # var hq_str_sh600487 或 _i
                raw = line.split('"')[1] if '"' in line else ""
                if not raw:
                    continue
                parts = raw.split(",")

                if "_i" not in var_name:
                    # 基本行情：名称、开盘、昨收、现价、最高、最低、成交量、成交额
                    if len(parts) >= 32:
                        data["name"] = parts[0]
                        data["open"] = _safe_float(parts[1])
                        data["pre_close"] = _safe_float(parts[2])
                        data["price"] = _safe_float(parts[3])
                        data["high"] = _safe_float(parts[4])
                        data["low"] = _safe_float(parts[5])
                        data["volume"] = _safe_float(parts[8])
                        data["amount"] = _safe_float(parts[9])
                        # 涨跌幅
                        price = data.get("price")
                        pre_close = data.get("pre_close")
                        if price and pre_close and pre_close > 0:
                            data["change_pct"] = round((price - pre_close) / pre_close * 100, 2)
                else:
                    # _i 扩展信息
                    # [5]=PE(TTM), [7]=流通市值(万元), [8]=流通股本(万股)
                    # [16]=每股净资产(BVPS), [32]=量比, [34]=行业, [37]=总市值(元)
                    if len(parts) > 16:
                        pe = _safe_float(parts[5])
                        bvps = _safe_float(parts[16])
                        data["pe"] = pe
                        # PB = 现价 / 每股净资产
                        price = data.get("price")
                        if price and bvps and bvps > 0:
                            data["pb"] = round(price / bvps, 2)
                    if len(parts) > 8:
                        float_cap_wan = _safe_float(parts[7])  # 流通市值(万元)
                        float_shares_wan = _safe_float(parts[8])  # 流通股本(万股)
                        if float_cap_wan:
                            data["float_cap"] = float_cap_wan * 10000  # 转为元
                        # 换手率 = 成交量 / 流通股本
                        vol = data.get("volume")
                        if vol and float_shares_wan and float_shares_wan > 0:
                            data["turnover"] = round(vol / (float_shares_wan * 10000) * 100, 2)
                    if len(parts) > 32:
                        data["volume_ratio"] = _safe_float(parts[32])
                    if len(parts) > 37:
                        data["market_cap"] = _safe_float(parts[37])  # 元
                    if len(parts) > 34:
                        data["industry"] = parts[34] if parts[34] else None

        except Exception as e:
            print(f"  ⚠️ hq.sinajs.cn 请求失败: {e}")

        if not data.get("price"):
            return {"name": self.code, "price": None}

        return data

    def analyze(self) -> dict:
        """
        生成基本面分析报告
        """
        d = self.data
        pe = d.get("pe")
        pb = d.get("pb")
        mkt_cap = d.get("market_cap")
        turnover = d.get("turnover")

        # ROE 近似
        roe = None
        if pe and pb and pe > 0:
            roe = round(pb / pe * 100, 2)

        # PE 评级
        pe_rating = "—"
        pe_comment = ""
        if pe is not None:
            if pe < 0:
                pe_rating = "亏损"
                pe_comment = "公司处于亏损状态，PE 为负"
            elif pe < 15:
                pe_rating = "低估"
                pe_comment = f"PE={pe:.1f}，估值较低，可能存在价值机会"
            elif pe < 30:
                pe_rating = "合理"
                pe_comment = f"PE={pe:.1f}，估值处于合理区间"
            elif pe < 60:
                pe_rating = "偏高"
                pe_comment = f"PE={pe:.1f}，估值偏高，需关注业绩支撑"
            else:
                pe_rating = "高估"
                pe_comment = f"PE={pe:.1f}，估值较高，注意风险"

        # PB 评级
        pb_rating = "—"
        pb_comment = ""
        if pb is not None:
            name = d.get("name", "")
            # 判断行业
            is_bank = "银行" in name
            is_realty = any(kw in name for kw in ["地产", "置业", "置地"])

            if is_bank:
                if pb < 0.6:
                    pb_rating = "深度低估"
                    pb_comment = f"银行股PB={pb:.2f}，深度破净"
                elif pb < 1.0:
                    pb_rating = "低估"
                    pb_comment = f"银行股PB={pb:.2f}，破净属正常区间"
                else:
                    pb_rating = "合理"
                    pb_comment = f"银行股PB={pb:.2f}"
            elif is_realty:
                if pb < 1.0:
                    pb_rating = "低估"
                    pb_comment = f"地产股PB={pb:.2f}，破净"
                else:
                    pb_rating = "合理"
                    pb_comment = f"地产股PB={pb:.2f}"
            else:
                if pb < 1:
                    pb_rating = "破净"
                    pb_comment = f"PB={pb:.2f}，低于净资产"
                elif pb < 3:
                    pb_rating = "合理"
                    pb_comment = f"PB={pb:.2f}，估值合理"
                elif pb < 8:
                    pb_rating = "偏高"
                    pb_comment = f"PB={pb:.2f}，偏高"
                else:
                    pb_rating = "高估"
                    pb_comment = f"PB={pb:.2f}，估值很高"

        # 市值分类
        cap_label = "—"
        if mkt_cap:
            if mkt_cap >= 1e12:
                cap_label = "超大盘"
            elif mkt_cap >= 5e10:
                cap_label = "大盘"
            elif mkt_cap >= 1e10:
                cap_label = "中盘"
            else:
                cap_label = "小盘"

        def _cap_str(v):
            if not v:
                return "—"
            if v >= 1e12:
                return f"{v / 1e12:.2f}万亿"
            if v >= 1e8:
                return f"{v / 1e8:.0f}亿"
            return f"{v:,.0f}"

        return {
            "name": d.get("name", self.code),
            "code": self.code,
            "price": d.get("price"),
            "change_pct": d.get("change_pct"),
            "valuation": {
                "pe": round(pe, 2) if pe else None,
                "pe_rating": pe_rating,
                "pe_comment": pe_comment,
                "pb": round(pb, 2) if pb else None,
                "pb_rating": pb_rating,
                "pb_comment": pb_comment,
                "roe": roe,
                "roe_comment": f"ROE≈{roe:.1f}%（PB/PE近似）" if roe else "无法计算",
            },
            "market": {
                "market_cap": _cap_str(mkt_cap),
                "float_cap": _cap_str(d.get("float_cap")),
                "cap_label": cap_label,
                "turnover": round(turnover, 2) if turnover else None,
                "volume_ratio": d.get("volume_ratio"),
            },
        }
