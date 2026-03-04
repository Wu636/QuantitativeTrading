from data.fetcher import DataFetcher
from data.processor import DataProcessor
from analyst.technical import TechnicalAnalyzer
import json

df = DataFetcher.get_index_daily('000001')
df = DataProcessor().prepare_backtest_data(df)
ta_result = TechnicalAnalyzer(df).analyze()
print(json.dumps(ta_result, indent=2, ensure_ascii=False))
