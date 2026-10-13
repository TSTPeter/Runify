import httpx
import respx

from runify import news

from .fixtures import NEWS_RSS


def test_parse_titles_and_links():
    headlines = news.parse(NEWS_RSS)
    assert headlines[0] == {"title": "Village fete crowns giant marrow champion", "url": "https://example.test/news/marrow"}
    assert len(headlines) == 3
    assert len(news.parse(NEWS_RSS, limit=2)) == 2


@respx.mock
def test_fetch_failure_means_no_news():
    respx.get(news.DEFAULT_FEED).mock(return_value=httpx.Response(503))
    with httpx.Client() as http:
        assert news.fetch(http) == []


@respx.mock
def test_fetch_bad_xml_means_no_news():
    respx.get(news.DEFAULT_FEED).mock(return_value=httpx.Response(200, text="<not rss"))
    with httpx.Client() as http:
        assert news.fetch(http) == []
