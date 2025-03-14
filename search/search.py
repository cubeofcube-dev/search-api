import abc
import requests
import asyncio
from typing import List, Dict, Any
from pydantic import BaseModel
from duckduckgo_search import DDGS
from .fetcher import ContentFetcher, RequestsHtmlFetcher
from .llm import LLMClient, GPTClient


class SearchResult(BaseModel):
    title: str
    link: str
    snippet: str
    content: str = None
    source_engine: str
    index: int = None


class SearchEngineConfig(BaseModel):
    api_key: str
    endpoint: str = ""
    params: Dict[str, Any] = {}


class SearchEngine(abc.ABC):
    def __init__(self, config: SearchEngineConfig):
        self.config = config

    @abc.abstractmethod
    def search(self, query: str, **kwargs) -> List[SearchResult]:
        pass


class GoogleSearch(SearchEngine):
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        headers = {}
        params = {
            "q": query,
            "key": self.config.api_key,
            **self.config.params
        }
        max_results = kwargs.get("max_results", None)
        if max_results:
            params["num"] = max_results
        
        response = requests.get(
            self.config.endpoint or "https://www.googleapis.com/customsearch/v1",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        
        return self._parse_results(response.json())

    def _parse_results(self, data: dict) -> List[SearchResult]:
        return [
            SearchResult(
                title=item["title"],
                link=item["link"],
                snippet=item["snippet"],
                source_engine="Google"
            ) for item in data.get("items", [])
        ]


class BingSearch(SearchEngine):
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        headers = {"Ocp-Apim-Subscription-Key": self.config.api_key}
        params = {
            "q": query,
            **self.config.params
        }

        max_results = kwargs.get("max_results", None)
        if max_results:
            params["count"] = max_results
        
        response = requests.get(
            self.config.endpoint or "https://api.bing.microsoft.com/v7.0/search",
            headers=headers,
            params=params
        )
        response.raise_for_status()
        
        return self._parse_results(response.json())

    def _parse_results(self, data: dict) -> List[SearchResult]:
        return [
            SearchResult(
                title=item["name"],
                link=item["url"],
                snippet=item["snippet"],
                source_engine="Bing"
            ) for item in data.get("webPages", {}).get("value", [])
        ]


class DuckDuckGoSearch(SearchEngine):
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        with DDGS() as ddgs:
            results = []
            search_params = {
                "safesearch": "off",
                "timelimit": "y",
                **self.config.params
            }

            max_results = kwargs.get("max_results", None)
            if max_results:
                search_params["max_results"] = max_results

            # for result in ddgs.text(query, **search_params):
            #     results.append(self._format_result(result))
            results.extend(self._parse_results(result) for result in ddgs.text(query, **search_params))
            
            return results

    def _parse_results(self, item: dict) -> SearchResult:
        def clean_text(text):
            return text.encode('utf-8', 'ignore').decode('utf-8').strip()

        return SearchResult(
            title=clean_text(item.get("title", "")),
            link=item.get("href", ""),
            snippet=clean_text(item.get("body", "")),
            source_engine="DuckDuckGo"
        )


class OmniSearchService:
    def __init__(self, fetcher: ContentFetcher, llm_cli: LLMClient):
        self.engines: Dict[str, SearchEngine] = {}
        self.fetcher = fetcher
        self.llm_cli = llm_cli
    
    def add_engine(self, name: str, engine: SearchEngine):
        self.engines[name] = engine
    
    async def search(self, query: str, **kwargs) -> List[SearchResult]:
        all_results = []
        fetch_content = kwargs.get("fetch_content", False)
        for engine_name, engine in self.engines.items():
            try:
                results = await engine.search(query, **kwargs)
                for i, r in enumerate(results):
                    r.index = i
                if fetch_content:
                    results = await self._fetch_content(results)
                all_results.extend(results)
            except Exception as e:
                print(f"Error searching with {engine_name}: {str(e)}")
        return all_results
    
    async def search_by_engine(self, engine_name: str, query: str, **kwargs) -> List[SearchResult]:
        if engine_name not in self.engines:
            raise ValueError(f"Engine {engine_name} not configured")
        fetch_content = kwargs.get("fetch_content", False)
        results = self.engines[engine_name].search(query, **kwargs)
        if fetch_content:
            results = await self._fetch_content(results)
        return results
    
    async def _fetch_content_by_search_result(self, r: SearchResult) -> SearchResult:
        try:
            raw_content = await asyncio.to_thread(self.fetcher.fetch, r.link)
            content = raw_content.clean_text

            import time
            begin = time.time()
            c = await self.llm_cli.completion([
                { "role": "system", "content": f"你是一个 HTML 数据清理员，请整理我提供的 HTML 文本中的有效信息，如果没有则返回 None" }, 
                { "role": "user", "content": content }])
            print("Completion Time elapsed:", time.time() - begin)

            r.content = c.choices[0].message.content
            return r
        except Exception as e:
            print(f"Error processing {r.link}: {str(e)}")
            return r
    
    async def _fetch_content(self, results: List[SearchResult]) -> List[SearchResult]:
        try:
            tasks = [self._fetch_content_by_search_result(r) for r in results]
            results = await asyncio.gather(*tasks)
            return results
        except Exception as e:
            print(f"Error fetching content: {str(e)}")
            return []


async def _test():
    o = OmniSearchService(RequestsHtmlFetcher(), GPTClient(model_name="gpt-4o-mini"))
    # import os
    # google_config = SearchEngineConfig(
    #     api_key=os.getenv("GOOGLE_API_KEY"),
    #     params={"cx": os.getenv("GOOGLE_CX")}
    # )
    # o.add_engine("google", GoogleSearch(google_config))


    # bing_config = SearchEngineConfig(
    #     api_key="your_bing_api_key"
    # )
    # o.add_engine("bing", BingSearch(bing_config))


    duckduckgo_config = SearchEngineConfig(
        api_key="",
        params={"region": "cn-zh",}
    )
    o.add_engine("duckduckgo", DuckDuckGoSearch(duckduckgo_config))

    import time
    begin = time.time()
    results = await o.search("武汉今天天气怎么样", max_results=1, fetch_content=False)
    print("Time elapsed:", time.time() - begin)
    print("Results count:", len(results))
    for result in results:
        print()
        print(result.model_dump_json(indent=2))

if __name__ == "__main__":
    import asyncio
    asyncio.run(_test())
