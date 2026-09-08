import os
import unittest
from unittest.mock import patch

from weixin_search_mcp.tools import weixin_search as ws


ANTISPIDER_BODY = (
    '<link rel="stylesheet" href="static/css/anti.min.css?v=1">'
    '<div id="seccodeRight"></div>'
)

RESULT_PAGE = """
<ul>
  <li id="sogou_vr_11002601_box_0">
    <div class="txt-box">
      <h3><a id="sogou_vr_11002601_title_0" href="/link?url=ABC">标题一</a></h3>
      <div class="s-p"><span class="s2">
        <script>document.write(timeConvert('1788797730'))</script>
      </span></div>
    </div>
  </li>
</ul>
"""


class FakeResponse:
    def __init__(self, text="", status_code=200, url="https://weixin.sogou.com/weixin"):
        self.text = text
        self.status_code = status_code
        self.url = url


class ReadableTimeTest(unittest.TestCase):
    def test_extracts_timestamp_from_unexecuted_js(self) -> None:
        raw = "document.write(timeConvert('1788797730'))"
        self.assertRegex(ws._readable_time(raw), r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")

    def test_keeps_plain_text_unchanged(self) -> None:
        self.assertEqual(ws._readable_time("  2026-09-08  "), "2026-09-08")

    def test_tolerates_empty_input(self) -> None:
        self.assertEqual(ws._readable_time(""), "")
        self.assertEqual(ws._readable_time(None), "")


class AntiSpiderTest(unittest.TestCase):
    """反爬拦截必须报错，不能伪装成「没有搜索结果」。"""

    def test_antispider_page_raises_instead_of_returning_empty(self) -> None:
        with patch.object(ws._SESSION, "get", return_value=FakeResponse(
            text=ANTISPIDER_BODY, url="https://weixin.sogou.com/antispider/?antip=wx_sh2")):
            with self.assertRaises(RuntimeError) as ctx:
                ws.sogou_weixin_search("任意关键词")
        self.assertIn("反爬", str(ctx.exception))

    def test_non_200_raises_even_when_not_strict(self) -> None:
        with patch.object(ws._SESSION, "get", return_value=FakeResponse(status_code=502)):
            with self.assertRaises(RuntimeError):
                ws.sogou_weixin_search("任意关键词", strict=False)

    def test_genuinely_empty_result_still_returns_empty_list(self) -> None:
        with patch.object(ws._SESSION, "get", return_value=FakeResponse(text="<ul></ul>")):
            self.assertEqual(ws.sogou_weixin_search("没有命中的关键词"), [])


class SessionReuseTest(unittest.TestCase):
    """真链解析必须复用发起搜索的同一 Session，且不带写死的 cookie。"""

    # 搜狗把真链拆成多段 JS 拼接，上游解析逻辑会丢弃第一段前缀、拼接其余段，
    # 再补回 "https://mp."。fixture 需与该格式一致。
    REAL_URL_SCRIPT = (
        "url += 'http://mp.';"
        "url += 'weixin.qq.com/s?src=11';"
        "url += '&timestamp=1788833897';"
    )

    def test_real_url_resolution_uses_shared_session(self) -> None:
        script = self.REAL_URL_SCRIPT
        with patch.object(ws._SESSION, "get", return_value=FakeResponse(text=script)) as m:
            url = ws.get_real_url_from_sogou("https://weixin.sogou.com/link?url=ABC")
        self.assertEqual(url, "https://mp.weixin.qq.com/s?src=11&timestamp=1788833897")
        self.assertTrue(m.called, "必须经由共享 Session 发出请求")

    def test_no_hardcoded_cookie_header(self) -> None:
        captured = {}

        def fake_get(url, headers=None, **kwargs):
            captured.update(headers or {})
            return FakeResponse(text=self.REAL_URL_SCRIPT)

        with patch.object(ws._SESSION, "get", side_effect=fake_get):
            ws.get_real_url_from_sogou("https://weixin.sogou.com/link?url=ABC")
        self.assertNotIn("Cookie", captured,
                         "不应写死 cookie：搜狗的跳转链与发起搜索的会话绑定")

    def test_search_parses_results_and_readable_time(self) -> None:
        with patch.object(ws._SESSION, "get", return_value=FakeResponse(text=RESULT_PAGE)), \
             patch.object(ws, "get_real_url_from_sogou", return_value="https://mp.weixin.qq.com/s?x=1"):
            results = ws.sogou_weixin_search("关键词")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["title"], "标题一")
        self.assertRegex(results[0]["publish_time"], r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")


class ProxyConfigTest(unittest.TestCase):
    def test_env_var_controls_trust_env(self) -> None:
        for value, expected in [("1", True), ("true", True), ("yes", True),
                                ("0", False), ("", False)]:
            with patch.dict(os.environ, {"WEIXIN_SEARCH_TRUST_ENV": value}):
                self.assertEqual(
                    os.environ.get("WEIXIN_SEARCH_TRUST_ENV", "").lower() in ("1", "true", "yes"),
                    expected, f"WEIXIN_SEARCH_TRUST_ENV={value!r}")


if __name__ == "__main__":
    unittest.main()
