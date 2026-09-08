import json
import os
import re
import datetime
import asyncio
from typing import Annotated, Any, Dict, List, Optional
import requests
from lxml import html
from urllib.parse import quote
import time

REQUEST_TIMEOUT = 15

_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
       '(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0')

# 搜狗把「跳转链」与发起搜索的会话绑定：解析真链必须复用同一 Session 的新鲜 cookie，
# 用另一个连接（或一份写死的旧 cookie）去请求跳转链只会拿到空结果。
_SESSION = requests.Session()

# 默认忽略 HTTP_PROXY/HTTPS_PROXY：常见代理的出口 IP 会被搜狗直接判为反爬，
# 表现为搜索恒返回空。确实需要经代理访问搜狗的用户可设 WEIXIN_SEARCH_TRUST_ENV=1 恢复。
_SESSION.trust_env = os.environ.get('WEIXIN_SEARCH_TRUST_ENV', '').lower() in ('1', 'true', 'yes')
_SESSION.headers.update({'User-Agent': _UA})


def _warmup():
    """访问一次首页，换取本次会话的新鲜 cookie。"""
    if not _SESSION.cookies:
        try:
            _SESSION.get('https://weixin.sogou.com/', timeout=REQUEST_TIMEOUT)
        except requests.RequestException:
            pass


def _readable_time(raw: str) -> str:
    """搜狗把发布时间塞在未执行的 JS 里：document.write(timeConvert('1788797730'))"""
    m = re.search(r"timeConvert\('(\d+)'\)", raw or '')
    if not m:
        return (raw or '').strip()
    return datetime.datetime.fromtimestamp(int(m.group(1))).strftime('%Y-%m-%d %H:%M')


def _is_antispider_response(response: requests.Response) -> bool:
    """Detect Sogou anti-spider pages that otherwise look like empty results."""
    final_url = response.url.lower()
    body = response.text.lower()
    return "antispider" in final_url or "seccoderight" in body or "anti.min.css" in body


def sogou_weixin_search(
    query: Annotated[str, "搜索关键词"],
    page: int = 1,
    strict: bool = False,
) -> List[Dict[str, str]]:
    """在搜狗微信搜索中搜索指定关键词并返回结果列表，包含真实URL

    Args:
        query: 搜索关键词
        page: 页码，默认1
    """
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Pragma': 'no-cache',
        'Referer': f'https://weixin.sogou.com/weixin?query={quote(query)}',
    }

    params = {
        'type': '2',
        's_from': 'input',
        'query': query,
        'ie': 'utf8',
        'page': page,
        '_sug_': 'n',
        '_sug_type_': '',
    }

    _warmup()

    try:
        response = _SESSION.get(
            'https://weixin.sogou.com/weixin',
            params=params,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )

        # 失败一律抛错：静默返回 [] 会让调用方把「被反爬拦截」误读成「该关键词没有文章」。
        if response.status_code != 200:
            raise RuntimeError(f"搜狗微信搜索返回异常状态码: {response.status_code}")

        if _is_antispider_response(response):
            raise RuntimeError("搜狗微信触发反爬验证：请降低频率或稍后重试（这不代表没有搜索结果）")

        tree = html.fromstring(response.text)
        results = []

        elements = tree.xpath("//a[contains(@id, 'sogou_vr_11002601_title_')]")
        publish_time = tree.xpath(
            "//li[contains(@id, 'sogou_vr_11002601_box_')]/div[@class='txt-box']/div[@class='s-p']/span[@class='s2']")

        for element, time_elem in zip(elements, publish_time):
            title = element.text_content().strip()
            link = element.get('href')
            if link and not link.startswith('http'):
                link = 'https://weixin.sogou.com' + link

            # 获取真实URL
            real_url = ""
            try:
                real_url = get_real_url_from_sogou(link)
            except Exception:
                pass

            results.append({
                'title': title,
                'link': link,
                'real_url': real_url,
                'publish_time': _readable_time(time_elem.text_content()),
                'page': str(page)  # str to match Dict[str, str] type signature
            })

        return results
    except RuntimeError:
        # 反爬拦截 / 异常状态码：必须向上传递，否则会被误读成「没有搜索结果」。
        raise
    except requests.RequestException as e:
        if strict:
            raise RuntimeError(f"请求搜狗微信搜索失败: {str(e)}") from e
        return []
    except Exception as e:
        if strict:
            raise RuntimeError(f"解析搜狗微信搜索结果失败: {str(e)}") from e
        return []


def sogou_weixin_search_all(query: str, max_pages: int = 10) -> List[Dict[str, str]]:
    """搜索所有页面的结果，自动翻页直到无结果或达到 max_pages

    Args:
        query: 搜索关键词
        max_pages: 最大页数，默认10
    Returns:
        List[Dict[str, str]]: 所有页的搜索结果
    """
    all_results = []
    for page in range(1, max_pages + 1):
        results = sogou_weixin_search(query, page=page, strict=True)
        if not results:
            break
        all_results.extend(results)
        # 避免请求过快被限流
        if page < max_pages:
            time.sleep(1)

    return all_results


def get_real_url_from_sogou(sogou_url: str) -> str:
    """从搜狗微信链接获取真实的微信公众号文章链接"""
    headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Referer': 'https://weixin.sogou.com/',
    }

    try:
        response = _SESSION.get(sogou_url, headers=headers, timeout=REQUEST_TIMEOUT)

        if _is_antispider_response(response):
            return ""

        script_content = response.text
        start_index = script_content.find("url += '") + len("url += '")
        url_parts = []
        while True:
            part_start = script_content.find("url += '", start_index)
            if part_start == -1:
                break
            part_end = script_content.find("'", part_start + len("url += '"))
            part = script_content[part_start + len("url += '"):part_end]
            url_parts.append(part)
            start_index = part_end + 1

        full_url = ''.join(url_parts).replace("@", "")
        if not full_url:
            return ""
        return "https://mp." + full_url
    except Exception as e:
        return ""


def get_real_url(sogou_url: Annotated[str, "搜狗微信链接,来自于sogou_weixin_search工具结果"]) -> str:
    """从搜狗微信链接获取真实的微信公众号文章链接"""
    return get_real_url_from_sogou(sogou_url)


def get_article_content(real_url: Annotated[str, "真实微信公众号文章链接"], referer: Annotated[Optional[str], "请求来源,get_real_url的返回值"]) -> str:
    """获取微信公众号文章的正文内容"""
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'cache-control': 'no-cache',
        'pragma': 'no-cache',
        'priority': 'u=0, i',
        'referer': referer,
        'sec-ch-ua': '"Microsoft Edge";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'document',
        'sec-fetch-mode': 'navigate',
        'sec-fetch-site': 'cross-site',
        'sec-fetch-user': '?1',
        'upgrade-insecure-requests': '1',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
    }
    if not referer:
        headers.pop('referer')

    try:
        if not real_url or real_url == "https://mp.":
            return "获取文章内容失败: 未拿到有效的微信公众号文章链接"

        response = _SESSION.get(real_url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        tree = html.fromstring(response.text)
        content_elements = tree.xpath("//div[@id='js_content']//text()")
        cleaned_content = [text.strip() for text in content_elements if text.strip()]
        main_content = '\n'.join(cleaned_content)
        return main_content
    except Exception as e:
        return f"获取文章内容失败: {str(e)}"

def get_wechat_article(query: str, number=10):
    """
    获取前10篇文章
    """
    start_time = time.time()
    results = sogou_weixin_search(query)
    if not results:
        return f"没有搜索到{query}相关的文章"
    articles = []
    results = results[:number]
    for every_result in results:
        sougou_link = every_result["link"]
        real_url = get_real_url(sougou_link)
        # referer：请求来源
        content = get_article_content(real_url, referer=sougou_link)
        article = {
            "title": every_result["title"],
            "publish_time": every_result["publish_time"],
            "real_url": real_url,
            "content": content
        }
        articles.append(article)
    end_time = time.time()
    print(f"关键词{query}相关的文章已经获取完毕，获取到{len(articles)}篇, 耗时{end_time - start_time}秒")
    return articles

if __name__ == '__main__':
    get_wechat_article(query="吉利汽车",number=2)
