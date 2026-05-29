"""
网络请求工具 v2
封装 httpx，提供：
  - 异步请求 + 连接池复用
  - 超时控制（可按需覆盖）
  - User-Agent 轮换（反检测）
  - 自动重试（指数退避）
  - 智能编码检测（解决 GBK 乱码）
  - Referer 伪装
"""
import asyncio
import logging
import random
import re
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# ── UA 池：覆盖手机/桌面/多浏览器，轮换使用 ────────────────────
_UA_POOL = [
    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    # Safari macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # iPhone Safari
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
    # Android Chrome
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
]

# 全局共享客户端（连接池复用）
_client: Optional[httpx.AsyncClient] = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(20.0, connect=8.0),
            follow_redirects=True,
            limits=httpx.Limits(max_connections=30, max_keepalive_connections=15),
            http2=False,   # 部分中文站不支持 H2
        )
    return _client


async def close_client():
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()


def _random_ua() -> str:
    return random.choice(_UA_POOL)


def _detect_encoding(response: httpx.Response) -> str:
    """
    智能检测编码，优先级：
    1. Content-Type header 声明
    2. HTML <meta charset> 标签
    3. 尝试 UTF-8 / GBK
    4. 兜底 UTF-8 replace
    """
    # 1. header
    ct = response.headers.get("content-type", "")
    m = re.search(r"charset=([^\s;]+)", ct, re.IGNORECASE)
    if m:
        return m.group(1).lower().replace("gb2312", "gbk")

    # 2. HTML meta（只扫前2KB）
    head = response.content[:2048]
    m = re.search(rb'charset=["\']?([^"\'>\s]+)', head, re.IGNORECASE)
    if m:
        enc = m.group(1).decode("ascii", errors="ignore").lower()
        return enc.replace("gb2312", "gbk")

    # 3. 启发式：含大量 \x80-\xff → 可能 GBK
    high_bytes = sum(1 for b in response.content[:500] if b > 0x7F)
    if high_bytes > 30:
        try:
            response.content.decode("gbk")
            return "gbk"
        except Exception:
            pass

    return "utf-8"


async def fetch_html(
    url: str,
    headers: Optional[dict] = None,
    encoding: Optional[str] = None,
    retries: int = 3,
    retry_delay: float = 1.0,
    referer: Optional[str] = None,
) -> Optional[str]:
    """
    抓取 HTML 页面

    :param url:         目标 URL
    :param headers:     额外请求头（会合并到默认头）
    :param encoding:    强制指定编码；None 则自动检测
    :param retries:     最大重试次数
    :param retry_delay: 首次重试等待秒数（后续指数退避）
    :param referer:     Referer 头，不传则用目标 URL 的 origin
    :return:            HTML 字符串，失败返回 None
    """
    client = get_client()

    # 构建 origin referer
    from urllib.parse import urlparse
    parsed = urlparse(url)
    default_referer = referer or f"{parsed.scheme}://{parsed.netloc}/"

    default_headers = {
        "User-Agent":      _random_ua(),
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.5,en;q=0.3",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer":         default_referer,
        "DNT":             "1",
        "Connection":      "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }
    if headers:
        default_headers.update(headers)

    for attempt in range(1, retries + 1):
        # 每次重试换一个 UA
        default_headers["User-Agent"] = _random_ua()
        try:
            response = await client.get(url, headers=default_headers)
            response.raise_for_status()

            enc = encoding or _detect_encoding(response)
            try:
                return response.content.decode(enc, errors="replace")
            except (LookupError, UnicodeDecodeError):
                return response.content.decode("utf-8", errors="replace")

        except httpx.TimeoutException:
            logger.warning(f"[HTTP] 超时 ({attempt}/{retries}): {url}")
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            logger.warning(f"[HTTP] {code} ({attempt}/{retries}): {url}")
            if 400 <= code < 500:   # 4xx 不重试
                return None
        except httpx.TooManyRedirects:
            logger.warning(f"[HTTP] 重定向过多: {url}")
            return None
        except Exception as e:
            logger.warning(f"[HTTP] 异常 ({attempt}/{retries}): {type(e).__name__}: {e}")

        if attempt < retries:
            wait = retry_delay * (2 ** (attempt - 1))   # 指数退避
            await asyncio.sleep(wait)

    logger.error(f"[HTTP] 全部重试失败: {url}")
    return None
