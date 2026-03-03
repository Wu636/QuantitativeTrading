"""
数据获取模块 - 使用 akshare 获取A股数据
"""

import os
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta


def _clear_proxy():
    """清除代理环境变量，避免国内 API 走代理连不上"""
    for key in ["http_proxy", "https_proxy", "all_proxy",
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        os.environ.pop(key, None)


class DataFetcher:
    """A股数据获取器"""

    @staticmethod
    def get_stock_daily(
        symbol: str,
        start_date: str = None,
        end_date: str = None,
        adjust: str = "qfq",
    ) -> pd.DataFrame:
        """
        获取个股日线行情数据

        Parameters
        ----------
        symbol : str
            股票代码，如 "000001"（平安银行）
        start_date : str
            开始日期，格式 "YYYYMMDD"，默认2年前
        end_date : str
            结束日期，格式 "YYYYMMDD"，默认今天
        adjust : str
            复权类型："qfq"前复权, "hfq"后复权, ""不复权

        Returns
        -------
        pd.DataFrame
            包含 date, open, close, high, low, volume, amount 等列
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")

        _clear_proxy()
        print(f"正在获取 {symbol} 的日线数据 ({start_date} ~ {end_date})...")

        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start_date,
                end_date=end_date,
                adjust=adjust,
            )
        except Exception as e:
            print(f"  ⚠️ akshare 获取失败 ({type(e).__name__})，使用 curl 回退...")
            df = DataFetcher._fetch_hist_via_curl(symbol, start_date, end_date, adjust)

        # 统一列名
        df = df.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "pct_change",
                "涨跌额": "change",
                "换手率": "turnover",
            }
        )

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        # 确保数值类型
        numeric_cols = ["open", "close", "high", "low", "volume", "amount"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        print(f"成功获取 {len(df)} 条数据")
        return df

    @staticmethod
    def _fetch_hist_via_curl(symbol, start_date, end_date, adjust="qfq"):
        """
        回退方案：使用新浪财经 K线 API 获取历史日线数据

        新浪接口一次最多返回约 1023 根 K 线，对绝大多数场景够用。
        scale=240 表示日线。
        """
        import subprocess
        import json
        from datetime import datetime

        prefix = "sh" if symbol.startswith(("6", "9")) else "sz"
        sina_symbol = f"{prefix}{symbol}"

        # 计算需要多少天
        try:
            d_start = datetime.strptime(start_date, "%Y%m%d")
            d_end = datetime.strptime(end_date, "%Y%m%d")
            datalen = max((d_end - d_start).days, 250)
            datalen = min(datalen, 1023)  # 新浪上限
        except Exception:
            datalen = 1023

        url = (
            f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?"
            f"symbol={sina_symbol}&scale=240&ma=no&datalen={datalen}"
        )

        print(f"  📡 使用新浪财经获取 {sina_symbol} 历史K线 (最近{datalen}天)...")

        result = subprocess.run(
            [
                "curl", "-s", "-m", "30",
                "--noproxy", "*",
                "-H", "User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "-H", "Referer: https://finance.sina.com.cn/",
                url,
            ],
            capture_output=True, text=True, timeout=35,
        )

        if result.returncode != 0 or not result.stdout.strip():
            raise ConnectionError(f"新浪历史K线获取失败: {result.stderr[:200]}")

        # 新浪返回的是 JS 格式的 JSON（带单引号 → 转双引号）
        raw = result.stdout.strip()
        raw = raw.replace("'", '"')

        try:
            klines = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError(f"新浪K线数据解析失败，原始返回: {raw[:200]}")

        if not klines:
            raise ValueError(f"未获取到 {symbol} 的历史数据")

        rows = []
        for k in klines:
            day = k.get("day", "")[:10]  # "2025-03-01 15:00:00" → "2025-03-01"
            o = float(k.get("open", 0))
            h = float(k.get("high", 0))
            l = float(k.get("low", 0))
            c = float(k.get("close", 0))
            v = int(float(k.get("volume", 0)))

            # 涨跌幅/额、成交额、换手率、振幅 - 新浪不直接给，后面自行计算
            rows.append({
                "日期": day,
                "开盘": o,
                "收盘": c,
                "最高": h,
                "最低": l,
                "成交量": v,
                "成交额": 0.0,     # 新浪K线不提供成交额
                "振幅": round((h - l) / c * 100, 2) if c else 0,
                "涨跌幅": 0.0,     # 后续在 DataFrame 中计算
                "涨跌额": 0.0,
                "换手率": 0.0,
            })

        df = pd.DataFrame(rows)

        # 补算涨跌幅
        if len(df) > 1:
            df["涨跌额"] = df["收盘"].diff()
            df["涨跌幅"] = df["收盘"].pct_change() * 100
            df = df.fillna(0)

        # 按日期范围过滤
        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
            df = df[(df["日期"] >= start_dt) & (df["日期"] <= end_dt)]
        except Exception:
            pass

        print(f"  ✅ 新浪财经返回 {len(df)} 条K线数据")
        return df

    @staticmethod
    def get_stock_name(symbol: str) -> str:
        """获取股票名称"""
        _clear_proxy()
        try:
            df = ak.stock_individual_info_em(symbol=symbol)
            name_row = df[df["item"] == "股票简称"]
            if not name_row.empty:
                return name_row["value"].values[0]
        except Exception:
            pass
        return symbol

    @staticmethod
    def get_index_daily(
        symbol: str = "000300",
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        获取指数日线数据（如沪深300，用于基准对比）

        Parameters
        ----------
        symbol : str
            指数代码，如 "000300"（沪深300）
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")

        _clear_proxy()
        print(f"正在获取指数 {symbol} 的日线数据...")

        df = ak.stock_zh_index_daily_em(symbol=f"sh{symbol}")

        df = df.rename(
            columns={
                "date": "date",
                "open": "open",
                "close": "close",
                "high": "high",
                "low": "low",
                "volume": "volume",
            }
        )

        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date").sort_index()

        # 按日期过滤
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]

        print(f"成功获取指数 {len(df)} 条数据")
        return df
