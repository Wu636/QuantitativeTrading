"""
数据获取模块 - 使用 akshare 获取A股数据
"""

import os
import akshare as ak
import pandas as pd
import re
from datetime import datetime, timedelta

_PROXY_ENV_CACHE = {}


def _clear_proxy():
    """清除代理环境变量，避免国内 API 走代理连不上"""
    for key in ["http_proxy", "https_proxy", "all_proxy",
                "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
        if key in os.environ:
            _PROXY_ENV_CACHE[key] = os.environ[key]
        os.environ.pop(key, None)


class DataFetcher:
    """A股数据获取器"""

    @staticmethod
    def resolve_stock_symbol(query: str) -> tuple[str, str]:
        """
        根据股票代码或名称解析 A 股代码。

        Returns
        -------
        tuple[str, str]
            (股票代码, 股票名称)
        """
        raw = (query or "").strip()
        if not raw:
            raise ValueError("请输入股票名称或代码")

        code_match = re.search(r"(\d{6})", raw)
        if code_match:
            symbol = code_match.group(1)
            return symbol, DataFetcher.get_stock_name(symbol)

        _clear_proxy()
        try:
            code_name_df = ak.stock_info_a_code_name()
            code_name_df = code_name_df.rename(columns={"code": "代码", "name": "名称"})
            matches = code_name_df[
                code_name_df["名称"].astype(str).str.contains(raw, case=False, regex=False)
            ]
            exact = matches[matches["名称"].astype(str) == raw]
            if not exact.empty:
                row = exact.iloc[0]
            elif not matches.empty:
                row = matches.iloc[0]
            else:
                raise ValueError(f"未找到股票：{raw}")

            return str(row["代码"]).zfill(6), str(row["名称"])
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"股票名称解析失败，请改用 6 位股票代码。原因：{exc}") from exc

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
        numeric_cols = [
            "open", "close", "high", "low", "volume", "amount",
            "amplitude", "pct_change", "change", "turnover",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        print(f"成功获取 {len(df)} 条数据")
        return df

    @staticmethod
    def get_market_index_daily(
        symbol: str,
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        获取基准指数日线数据。

        Parameters
        ----------
        symbol : str
            指数代码，可传 sh000002、sz399107、000002 等。
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y%m%d")
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=730)).strftime("%Y%m%d")

        raw_symbol = str(symbol).strip().lower()
        if raw_symbol.startswith(("sh", "sz")):
            index_symbol = raw_symbol
        elif raw_symbol.startswith(("399", "159", "399")):
            index_symbol = f"sz{raw_symbol}"
        else:
            index_symbol = f"sh{raw_symbol}"

        _clear_proxy()
        print(f"正在获取指数 {index_symbol} 的日线数据...")

        try:
            df = DataFetcher._fetch_index_via_sina(index_symbol, start_date, end_date)
        except Exception as e:
            print(f"  ⚠️ 新浪指数获取失败 ({type(e).__name__})，尝试 akshare 指数接口...")
            df = ak.stock_zh_index_daily_em(symbol=index_symbol)

        df = df.rename(
            columns={
                "date": "date",
                "open": "open",
                "close": "close",
                "high": "high",
                "low": "low",
                "volume": "volume",
                "amount": "amount",
            }
        )

        if "date" not in df.columns:
            raise ValueError(f"指数 {index_symbol} 返回数据缺少日期列")

        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date").sort_index()

        for col in ["open", "close", "high", "low", "volume", "amount"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        df = df[(df.index >= start_dt) & (df.index <= end_dt)]

        print(f"成功获取指数 {len(df)} 条数据")
        return df

    @staticmethod
    def get_sina_realtime_quote(symbol: str) -> dict | None:
        """获取新浪实时行情，返回 price/pre_close/pct/date 等字段。"""
        import subprocess

        raw_symbol = str(symbol).strip().lower()
        if raw_symbol.startswith(("sh", "sz")):
            sina_symbol = raw_symbol
        elif raw_symbol.startswith(("6", "9", "000")):
            sina_symbol = f"sh{raw_symbol}"
        else:
            sina_symbol = f"sz{raw_symbol}"

        result = subprocess.run(
            [
                "curl", "-s", "-m", "10",
                "--noproxy", "*",
                "-H", "User-Agent: Mozilla/5.0",
                "-H", "Referer: https://finance.sina.com.cn/",
                f"https://hq.sinajs.cn/list={sina_symbol}",
            ],
            capture_output=True, timeout=12,
        )
        if result.returncode != 0 or not result.stdout:
            return None

        text = result.stdout.decode("gbk", errors="replace").strip()
        if '"' not in text:
            return None
        raw = text.split('"')[1]
        parts = raw.split(",")
        if len(parts) < 32 or not parts[3]:
            return None

        def safe_float(value):
            try:
                return float(value)
            except Exception:
                return None

        price = safe_float(parts[3])
        pre_close = safe_float(parts[2])
        if not price or not pre_close:
            return None

        return {
            "symbol": sina_symbol,
            "name": parts[0],
            "open": safe_float(parts[1]),
            "pre_close": pre_close,
            "price": price,
            "high": safe_float(parts[4]),
            "low": safe_float(parts[5]),
            "volume": safe_float(parts[8]),
            "amount": safe_float(parts[9]),
            "pct_change": (price / pre_close - 1) * 100,
            "date": parts[30] if len(parts) > 30 else None,
            "time": parts[31] if len(parts) > 31 else None,
        }

    @staticmethod
    def append_realtime_quote(daily: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """把新浪实时行情作为当日最新一行拼到日线数据中。"""
        quote = DataFetcher.get_sina_realtime_quote(symbol)
        if not quote or not quote.get("date"):
            return daily

        quote_date = pd.to_datetime(quote["date"], errors="coerce")
        if pd.isna(quote_date):
            return daily

        df = daily.copy().sort_index()
        last_date = df.index[-1] if not df.empty else None
        if last_date is not None and quote_date < last_date:
            return df

        df.loc[quote_date, "open"] = quote.get("open")
        df.loc[quote_date, "close"] = quote.get("price")
        df.loc[quote_date, "high"] = quote.get("high")
        df.loc[quote_date, "low"] = quote.get("low")
        df.loc[quote_date, "volume"] = quote.get("volume")
        df.loc[quote_date, "amount"] = quote.get("amount")
        df.loc[quote_date, "pct_change"] = quote.get("pct_change")
        return df.sort_index()

    @staticmethod
    def _fetch_index_via_sina(symbol: str, start_date: str, end_date: str):
        """使用新浪财经 K 线接口获取指数日线。"""
        import subprocess
        import json
        from datetime import datetime

        raw_symbol = str(symbol).strip().lower()
        sina_symbol = raw_symbol if raw_symbol.startswith(("sh", "sz")) else f"sh{raw_symbol}"

        try:
            d_start = datetime.strptime(start_date, "%Y%m%d")
            d_end = datetime.strptime(end_date, "%Y%m%d")
            datalen = max((d_end - d_start).days, 250)
            datalen = min(datalen, 1023)
        except Exception:
            datalen = 1023

        url = (
            f"https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
            f"CN_MarketData.getKLineData?"
            f"symbol={sina_symbol}&scale=240&ma=no&datalen={datalen}"
        )

        result = subprocess.run(
            [
                "curl", "-s", "-m", "30",
                "--noproxy", "*",
                "-H", "User-Agent: Mozilla/5.0",
                "-H", "Referer: https://finance.sina.com.cn/",
                url,
            ],
            capture_output=True, text=True, timeout=35,
        )
        if result.returncode != 0 or not result.stdout.strip():
            raise ConnectionError(f"新浪指数K线获取失败: {result.stderr[:200]}")

        raw = result.stdout.strip().replace("'", '"')
        klines = json.loads(raw)
        if not klines:
            raise ValueError(f"未获取到指数 {symbol} 的历史数据")

        rows = []
        for k in klines:
            day = k.get("day", "")[:10]
            rows.append({
                "date": day,
                "open": float(k.get("open", 0)),
                "close": float(k.get("close", 0)),
                "high": float(k.get("high", 0)),
                "low": float(k.get("low", 0)),
                "volume": float(k.get("volume", 0)),
                "amount": 0.0,
            })

        df = pd.DataFrame(rows)
        try:
            start_dt = datetime.strptime(start_date, "%Y%m%d").strftime("%Y-%m-%d")
            end_dt = datetime.strptime(end_date, "%Y%m%d").strftime("%Y-%m-%d")
            df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]
        except Exception:
            pass
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
