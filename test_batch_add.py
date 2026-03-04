import requests
import json

base_url = "http://localhost:8000/api/watchlist"

payload = {
    "stocks": [
        {"code": "600519", "name": "贵州茅台", "group": "核心资产"},
        {"code": "300750", "name": "宁德时代", "group": "核心资产"}
    ]
}

try:
    res = requests.post(f"{base_url}/batch", json=payload)
    print("Batch add status:", res.status_code)
    print("Response:", res.json())
except Exception as e:
    print("Error:", e)
