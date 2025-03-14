import abc
import requests
from pydantic import BaseModel
from bs4 import BeautifulSoup


class FetchedContent(BaseModel):
    url: str
    raw_content: str = ""
    clean_text: str = ""
    status_code: int = 0
    error: str = ""


class ContentFetcher(abc.ABC):
    @abc.abstractmethod
    def fetch(self, url: str) -> FetchedContent:
        pass


class SimpleFetcher(ContentFetcher):
    def __init__(self, timeout=10, headers=None):
        self.timeout = timeout
        self.headers = headers or {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }

    def fetch(self, url: str) -> FetchedContent:
        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            return FetchedContent(
                url=url,
                raw_content=response.text,
                clean_text=self._clean_text(response.text),
                status_code=response.status_code
            )
        except Exception as e:
            return FetchedContent(url=url, error=str(e))

    def _clean_text(self, html: str) -> str:
        try:
            encoding = requests.utils.get_encodings_from_content(html)[0]
        except:
            encoding = 'utf-8'
        html = html.encode(encoding, errors='replace').decode('utf-8', errors='replace')
        soup = BeautifulSoup(html, 'lxml', from_encoding='utf-8')

        # 移除不需要的元素
        for tag in ['script', 'style', 'noscript', 'meta', 'link']:
            for element in soup.find_all(tag):
                element.decompose()

        # 获取处理后的文本
        text = soup.get_text(separator='\n', strip=True)

        # 清理空白并保留中文标点
        return '\n'.join([line.strip() for line in text.split('\n') if line.strip()])


class RequestsHtmlFetcher(ContentFetcher):
    def __init__(self, render=False, timeout=10):
        from requests_html import HTMLSession
        self.session = HTMLSession()
        self.render = render
        self.timeout = timeout

    def fetch(self, url: str) -> FetchedContent:
        try:
            response = self.session.get(url, timeout=self.timeout)
            if self.render:
                response.html.render(timeout=self.timeout)
                
            return FetchedContent(
                url=url,
                raw_content=response.text,
                clean_text=response.html.text,
                status_code=response.status_code
            )
        except Exception as e:
            return FetchedContent(url=url, error=str(e))
        finally:
            self.session.close()


if __name__ == "__main__":

    link = "https://ai.com/"

    # fetcher = SimpleFetcher()
    # content = fetcher.fetch(link)
    # print(content)
    # print(content.clean_text)

    fetcher = RequestsHtmlFetcher()
    content = fetcher.fetch(link)
    print(content)
    print(content.clean_text)
