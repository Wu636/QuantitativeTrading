"""
LLM 客户端 — 统一封装 OpenAI 兼容接口

支持 OpenAI / DeepSeek / 通义千问 / 文心一言 等任何 OpenAI 兼容服务。

使用方式：
    在项目根目录创建 .env 文件：
        LLM_API_KEY=sk-xxxxxxx
        LLM_BASE_URL=https://api.deepseek.com/v1    # 可选，默认 OpenAI
        LLM_MODEL=deepseek-chat                      # 可选，默认 gpt-4o
"""

import os
import json
import httpx
from pathlib import Path


def _load_env():
    """从项目根目录 .env 文件加载环境变量（简易实现，无需 python-dotenv）"""
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value:
                    os.environ.setdefault(key, value)


# 启动时自动加载
_load_env()


def get_llm_config() -> dict:
    """获取 LLM 配置"""
    return {
        "api_key": os.environ.get("LLM_API_KEY", ""),
        "base_url": os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
        "model": os.environ.get("LLM_MODEL", "gpt-4o"),
    }


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    stream: bool = False,
) -> str:
    """
    调用 LLM 生成分析报告

    Parameters
    ----------
    system_prompt : str
        系统提示词（角色设定）
    user_prompt : str
        用户提示词（包含数据和分析请求）
    temperature : float
        生成温度（越低越确定性）
    max_tokens : int
        最大输出 token 数
    stream : bool
        是否使用流式响应

    Returns
    -------
    str
        LLM 生成的完整文本，或者流式生成器
    """
    config = get_llm_config()

    if not config["api_key"]:
        raise ValueError(
            "未配置 LLM API Key！\n"
            "请在项目根目录创建 .env 文件，写入：\n"
            "  LLM_API_KEY=sk-xxxxxxx\n"
            "  LLM_BASE_URL=https://api.deepseek.com/v1\n"
            "  LLM_MODEL=deepseek-chat"
        )

    base = config['base_url'].rstrip('/')
    # 自动补 /v1 —— 用户若只填了 https://api.deepseek.com 也能正常工作
    if not base.endswith('/v1'):
        base = base + '/v1'
    url = f"{base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if stream:
        return _stream_llm(url, headers, payload)

    # 非流式：直接返回完整文本
    async with httpx.AsyncClient(timeout=120, proxy=None) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            print(f"❌ LLM API 返回 {resp.status_code}: {resp.text[:500]}")
            resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _stream_llm(url: str, headers: dict, payload: dict):
    """
    SSE 流式生成器 — yield 每个 token 片段

    用于前端实现打字机效果
    """
    async with httpx.AsyncClient(timeout=120, proxy=None) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                print(f"❌ LLM Stream API 返回 {resp.status_code}: {body[:500]}")
                resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    delta = chunk["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield content
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
