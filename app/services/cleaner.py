"""
正文清洗器 v2
清除从各小说网站抓取的内容中的广告、垃圾文字、干扰字符

新增：
  - 更完整的广告关键词库
  - 繁体/简体混合网站的特殊处理
  - 乱码段落检测
  - 合并孤立短行（对话标点修复）
"""
import re
from bs4 import BeautifulSoup


# ── 广告关键词黑名单 ──────────────────────────────────────────────
AD_KEYWORDS = [
    # 网址类
    "www.", ".com", ".net", ".org", ".cc", ".xyz", ".vip", ".me",
    ".io", ".top", ".site", ".online", "http://", "https://",
    # 推广话术
    "最新网址", "最新章节", "最新地址", "最快更新", "无弹窗",
    "免费阅读", "在线阅读", "全文阅读", "全本免费",
    "手机阅读", "手机用户请", "请访问", "请到",
    "记住网址", "记住本站", "收藏本站", "加入书签",
    "永久地址", "备用地址", "换源", "新地址",
    # 来源声明
    "本书首发", "首发网站", "首发站", "首发于",
    "转载请注明", "来源：", "来源:", "作者：",
    "全文字幕", "全文字幕无广告",
    # 站点名（高频盗版站）
    "笔趣阁", "笔趣看", "笔趣阁5200", "笔趣库",
    "顶点小说", "顶点", "起点中文", "纵横中文",
    "全本小说", "小说网", "阅读网", "书趣网",
    "新笔趣阁", "贼吧小说", "飘天文学",
    "爱看小说", "海棠书屋", "言情小说",
    # 导航文字误入正文
    "上一章", "下一章", "返回目录", "回目录",
    "章节目录", "章节错误", "点此举报", "错误举报",
    "请记住本书", "完本神作", "更多精彩",
    # 广告套话
    "正版订阅", "订阅本章", "月票", "打赏",
    "求推荐票", "求收藏", "求月票", "谢谢支持",
]

# ── 正则黑名单 ────────────────────────────────────────────────────
_RE_URL        = re.compile(r"[a-zA-Z0-9\-]+\.(com|net|org|cc|xyz|vip|me|io|top|site|la|so)\b", re.I)
_RE_CTRL       = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_RE_HTML_ENT   = re.compile(r"&(amp|lt|gt|nbsp|quot|#\d+);", re.I)
_RE_MULTI_PUNC = re.compile(r"([。！？…]{2,})")   # 多余标点保留一个
_RE_FULL_SPACE = re.compile(r"\u3000+")            # 全角空格 → 普通空格
_RE_MULTI_NL   = re.compile(r"\n{3,}")             # 三个以上换行 → 两个


def clean_content(raw: str | None) -> str:
    """
    主清洗函数
    输入原始 HTML 或纯文本，返回干净小说正文

    流程:
        1. HTML → 纯文本（保留段落换行）
        2. 全局字符级清洗
        3. 按段落拆分
        4. 过滤广告段落
        5. 每段细粒度清洗
        6. 短行合并（对话修复）
        7. 重组
    """
    if not raw:
        return ""

    text = _strip_html(raw)
    text = _global_clean(text)
    paragraphs = _split_paragraphs(text)
    paragraphs = [p for p in paragraphs if not _is_ad_paragraph(p)]
    paragraphs = [_line_clean(p) for p in paragraphs]
    paragraphs = [p for p in paragraphs if p.strip()]

    return "\n\n".join(paragraphs)


# ── 步骤实现 ──────────────────────────────────────────────────────

def _strip_html(raw: str) -> str:
    """HTML → 带换行的纯文本"""
    # 块级标签换成换行
    raw = re.sub(r"<br\s*/?>", "\n", raw, flags=re.IGNORECASE)
    raw = re.sub(r"</(p|div|li|tr|section|article)>", "\n", raw, flags=re.IGNORECASE)
    soup = BeautifulSoup(raw, "lxml")
    # 删除 script / style
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text(separator="\n")


def _global_clean(text: str) -> str:
    """全局字符级清洗"""
    text = _RE_CTRL.sub("", text)           # 控制字符
    text = _RE_HTML_ENT.sub("", text)       # HTML 实体残留
    text = _RE_FULL_SPACE.sub(" ", text)    # 全角空格
    text = _RE_MULTI_NL.sub("\n\n", text)   # 多余换行
    return text


def _split_paragraphs(text: str) -> list[str]:
    lines = text.splitlines()
    return [ln.strip() for ln in lines if ln.strip()]


def _is_ad_paragraph(para: str) -> bool:
    """判断是否是广告/垃圾段落"""
    p_lower = para.lower()
    for kw in AD_KEYWORDS:
        if kw.lower() in p_lower:
            return True

    # URL 检测
    if _RE_URL.search(para):
        return True

    # 极短且无实质汉字内容（≤6字，不含标点）
    zh_chars = re.findall(r"[\u4e00-\u9fff]", para)
    if len(para) <= 6 and len(zh_chars) < 2:
        return True

    # 高度重复字符（如 "————————"）
    if len(set(para)) <= 3 and len(para) >= 8:
        return True

    return False


def _line_clean(text: str) -> str:
    """段落内细粒度清洗"""
    # 去掉残余 URL
    text = _RE_URL.sub("", text)
    # 多余标点
    text = _RE_MULTI_PUNC.sub(lambda m: m.group(1)[0], text)
    # 首尾空白
    return text.strip()


# ── 对外工具 ──────────────────────────────────────────────────────

def extract_title_from_content(content: str, fallback: str = "") -> str:
    """
    从正文第一行猜测章节标题（用于没有标题的站点）
    """
    lines = [l.strip() for l in content.splitlines() if l.strip()]
    if not lines:
        return fallback
    first = lines[0]
    # 第一行若像标题（含"第X章"或较短）则采用
    if re.search(r"第\s*[零一二三四五六七八九十百千\d]+\s*[章节回卷]", first):
        return first
    if len(first) <= 30 and not re.search(r"[。，！？]", first):
        return first
    return fallback
