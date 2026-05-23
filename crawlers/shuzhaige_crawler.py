"""
书斋阁（www.shuzhaige.com）爬虫适配器
继承 BaseCrawler，实现搜索、获取章节列表、获取正文三大功能
"""

import re
import time
import requests
from typing import List, Dict, Optional
from bs4 import BeautifulSoup
from .base_crawler import BaseCrawler


class ShuzhaigeCrawler(BaseCrawler):
    """书斋阁网站爬虫"""

    BASE_URL = "https://www.shuzhaige.com"

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    MAX_RETRIES = 3
    REQUEST_INTERVAL = 1

    # 中文书名 -> 拼音路径 映射表（覆盖大部分热门小说）
    BOOK_PATH_MAP = {
        "Beta她是大总攻[ABO]": "3327",
        "[原神]为什么我遇见迪卢克的打开方式和你们不太一样": "3064",
        "专属密码": "1639",
        "世味成茶[快穿]": "3343",
        "丧尸袭城之后[天灾]": "3329",
        "亡国皇后穿成反贼后": "3317",
        "京华烟云": "180",
        "人世间": "renshijian",
        "人民的名义": "renmindemingyi",
        "位面掮客": "2100",
        "倾世皇妃": "qingshihuangfei",
        "偏偏惹你": "3339",
        "划水三年,一朝成神": "3340",
        "前男友他不太对劲": "2706",
        "北城霜降": "3337",
        "危险关系": "weixianguanxi",
        "历史直播,开幕暴击": "2914",
        "古董局中局": "gudongjuzhongju",
        "哥哥，你养我吧！": "1670",
        "大佬与厉鬼都被对方吓晕了": "3344",
        "她是许愿机[快穿]": "3335",
        "局外人": "juwairen",
        "山河表里": "shanhebiaoli",
        "庆余年": "qingyunian",
        "开端": "kaiduan",
        "总把反派欺负哭（穿书）": "3331",
        "我们仨": "womensa",
        "我咬不动她": "3328",
        "我在山海世界饲养凶兽[全息]": "3326",
        "我在恐怖游戏里开宾馆": "3333",
        "我爹叫岳飞": "3342",
        "掉马后他悔不当初": "3341",
        "摇光": "2377",
        "斗破苍穹": "doupocangqiong",
        "斗罗大陆": "douluodalu",
        "暂坐": "zanzuo",
        "暗恋外交官[婚后追妻]": "3332",
        "炮灰不好当[快穿]": "1710",
        "炼剑": "3330",
        "玉楼春": "yulouchun",
        "盛夏晚晴天": "shengxiawanqingtian",
        "穿为年代文的炮灰美人": "3336",
        "穿书后我成了年代文女主她妯娌[七零]": "3325",
        "穿到星际后我成了虫母": "3334",
        "老妹挺穷啊": "3338",
        "金婚": "jinhun",
        "长日吟情": "2837",
        "长相思": "changxiangsi",
        "雪中悍刀行": "xuezhonghandaoxing",
        "魔道祖师": "modaozushi",
        "龙族1·火之晨曦": "longzu1huozhichenxi",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self._last_request_time = 0

    def _request_with_retry(self, url: str) -> Optional[requests.Response]:
        """带重试机制的HTTP请求"""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.REQUEST_INTERVAL:
            time.sleep(self.REQUEST_INTERVAL - elapsed)

        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                response = self.session.get(url, timeout=15)
                response.encoding = "utf-8"
                response.raise_for_status()
                self._last_request_time = time.time()
                return response
            except Exception as e:
                print(f"[爬虫] 请求失败 (第{attempt}次): {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(2 ** attempt)
        return None

    def search(self, keyword: str) -> List[Dict[str, str]]:
        """
        搜索小说 - 多策略查找
        策略1: 通过拼音映射表直接访问（如 doupocangqiong）
        策略2: 从首页和分类页面查找匹配的小说
        """
        results = []

        # ---- 策略1: 拼音路径直接访问 ----
        pinyin_path = self.BOOK_PATH_MAP.get(keyword)
        if pinyin_path:
            try_url = f"{self.BASE_URL}/{pinyin_path}/"
            response = self._request_with_retry(try_url)
            if response:
                soup = BeautifulSoup(response.text, "html.parser")
                title_tag = soup.find("title")
                if title_tag and "404" not in title_tag.string:
                    # 从标题提取作者: "斗破苍穹全文阅读-天蚕土豆-..."
                    author = "未知"
                    match = re.search(r"阅读[-_\u2014]([^\-\u2014_]+)", title_tag.string)
                    if match:
                        author = match.group(1).strip()
                    results.append({
                        "title": keyword,
                        "author": author,
                        "url": try_url,
                        "latest_chapter": "",
                    })
                    print(f"[爬虫] 通过拼音路径找到: {keyword} - {author}")
                    return results

        # ---- 策略2: 从首页查找 ----
        response = self._request_with_retry(self.BASE_URL)
        if response:
            soup = BeautifulSoup(response.text, "html.parser")
            seen_urls = set()
            for a in soup.find_all("a"):
                href = a.get("href", "")
                text = a.get_text().strip()
                if not href or not text:
                    continue
                if keyword not in text:
                    continue
                if href.startswith("http"):
                    full_url = href
                elif href.startswith("/"):
                    full_url = self.BASE_URL + href
                else:
                    full_url = self.BASE_URL + "/" + href
                if full_url in seen_urls or ".html" in full_url:
                    continue
                seen_urls.add(full_url)
                results.append({
                    "title": text,
                    "author": "未知",
                    "url": full_url,
                    "latest_chapter": "",
                })

        print(f"[爬虫] 搜索 \"{keyword}\" 找到 {len(results)} 个结果")
        return results

    def get_chapters(self, book_url: str) -> List[Dict[str, str | int]]:
        """获取动漫小说章节列表"""
        response = self._request_with_retry(book_url)
        if not response:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        chapters = []

        # 章节列表在 <ul> 下的 <li> 中
        for ul in soup.find_all("ul"):
            lis = ul.find_all("li")
            if len(lis) > 5:  # 找到章节列表所在的ul
                for idx, li in enumerate(lis, 1):
                    a = li.find("a")
                    if not a:
                        continue
                    href = a.get("href", "")
                    title = a.get_text().strip()
                    if not href or not title:
                        continue

                    if href.startswith("http"):
                        url = href
                    elif href.startswith("/"):
                        url = self.BASE_URL + href
                    else:
                        base = book_url.rstrip("/")
                        url = base + "/" + href.lstrip("/")

                    chapters.append({"title": title, "url": url, "index": idx})
                break  # 找到章节列表就退出

        print(f"[爬虫] 获取到章节列表: {len(chapters)} 章")
        return chapters

    def get_content(self, chapter_url: str) -> Dict[str, str]:
        """获取章节正文内容"""
        response = self._request_with_retry(chapter_url)
        if not response:
            return {"title": "获取失败", "content": ""}

        soup = BeautifulSoup(response.text, "html.parser")

        # 提取章节标题
        title = ""
        h1 = soup.find("h1")
        if h1:
            title = h1.get_text().strip()
        if not title:
            t = soup.find("title")
            if t:
                title = re.sub(r"[-_\u2014].*$", "", t.get_text()).strip()

        # 提取正文内容
        content_div = soup.find("div", id="content")
        content_text = ""

        if content_div:
            html = str(content_div)
            # 清理HTML标签
            html = re.sub(r"<br\s*/?>", "\n", html)
            html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
            html = re.sub(r"<[^>]+>", "", html)
            html = html.replace("&nbsp;", " ")
            html = re.sub(r"\n{3,}", "\n\n", html)
            content_text = html.strip()
            # 清理导航文字和广告
            lines = content_text.split("\n")
            clean_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                # 跳过导航行
                if "上一章" in line or "下一章" in line or "返回列表" in line:
                    continue
                # 跳过广告行
                if "马上记住" in line or "书斋阁" in line or "www.shuzhaige" in line:
                    continue
                if "退出阅" in line or "阅/读模式" in line:
                    continue
                clean_lines.append(line)
            content_text = "\n".join(clean_lines)
        else:
            content_text = soup.get_text(separator="\n", strip=True)

        print(f"[爬虫] 获取章节: {title} ({len(content_text)} 字符)")
        return {"title": title, "content": content_text}
