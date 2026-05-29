"""
站点注册表
集中管理所有已知小说站的域名 → 解析器类型 的映射
新增站点只需在这里加一行，无需改其他代码
"""
from typing import Optional
from urllib.parse import urlparse

# 域名 → 解析器类型ID 映射表
# 格式：{ "解析器ID": ["domain1", "domain2", ...] }
DOMAIN_REGISTRY: dict[str, list[str]] = {
    # 笔趣阁系列（同源，页面结构一致）
    "biquge": [
        "biquge.com", "biquge.cc", "biquge.info", "biquge.biz",
        "biquge.us", "biqugee.cc", "biquge5200.com", "biquge.tv",
        "biquge.org", "www.biquge.cc",
    ],
    # 新笔趣阁系列
    "xbiquge": [
        "xbiquge.so", "xbiquge.la", "xbiquge.cc", "xbiquge.com",
        "xbiquge.net", "xbiquge5.com",
    ],
    # 69书吧
    "69shu": [
        "69shu.com", "69shu.net", "69shuba.cx", "69shuba.com",
        "www.69shu.pro",
    ],
    # 趣啦
    "qu": [
        "qu.la", "qula.cc", "www.qu.la",
    ],
    # 顶点小说
    "dingdian": [
        "dingdiann.com", "23us.com", "23us.cc", "23qb.com",
        "ddxs.com", "23xsw.com",
    ],
    # 飘天文学
    "piaotian": [
        "piaotian.com", "piaotia.com", "ptwxz.com",
        "piaotianwenxue.com",
    ],
    # 书趣阁
    "shuqu": [
        "shuqu.net", "shuqu.cc",
    ],
    # 笔下文学
    "bixia": [
        "bixia.net", "bxwx.net", "bxwx.org",
    ],
    # 小说18
    "xs18": [
        "xs18.net", "xs18.cc",
    ],
    # 81中文
    "81zw": [
        "81zw.com", "81zw.cc",
    ],
}

# 构建反查表：domain → parser_id（加速查询）
_DOMAIN_TO_PARSER: dict[str, str] = {}
for _pid, _domains in DOMAIN_REGISTRY.items():
    for _d in _domains:
        _DOMAIN_TO_PARSER[_d.lower().lstrip("www.")] = _pid


def detect_parser_id(url: str) -> Optional[str]:
    """根据 URL 返回对应的解析器 ID，未知站点返回 None"""
    try:
        host = urlparse(url).netloc.lower().lstrip("www.")
    except Exception:
        return None
    # 精确匹配
    if host in _DOMAIN_TO_PARSER:
        return _DOMAIN_TO_PARSER[host]
    # 后缀匹配（处理子域名）
    for domain, pid in _DOMAIN_TO_PARSER.items():
        if host.endswith(domain):
            return pid
    return None


def all_domains() -> list[str]:
    """返回所有已知域名（用于构造 site: 搜索过滤）"""
    result = []
    for domains in DOMAIN_REGISTRY.values():
        result.extend(domains)
    return result


def site_filter_query() -> str:
    """返回 Yandex/Bing 的 site: 过滤字符串"""
    # 每个站点只取第一个主域名，避免 query 太长
    primary_domains = [domains[0] for domains in DOMAIN_REGISTRY.values()]
    return " OR ".join(f"site:{d}" for d in primary_domains)
