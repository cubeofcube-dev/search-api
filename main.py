import os
import time
import json
import hashlib
from fastapi import FastAPI, Request, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from search.fetcher import RequestsHtmlFetcher
from search.llm import GPTClient
from search.search import SearchResult
from utils.logger import logger
from search import OmniSearchService, SearchEngineConfig, DuckDuckGoSearch, GoogleSearch, BingSearch
from cache.redis import RedisClient
from dotenv import load_dotenv

load_dotenv()

redis_cli = RedisClient(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

app = FastAPI()
security = HTTPBearer()


async def auth(req: Request, c: HTTPAuthorizationCredentials = Depends(security)):
    white_list = ["/", "/v1/health"]
    if req.url.path in white_list:
        return

    if os.environ.get("API_KEY", "") == "":
        return

    if c.scheme != "Bearer" or c.credentials != os.environ.get("API_KEY"):
        raise HTTPException(status_code=403, detail="Forbidden")


@app.middleware("http")
async def add_process_time_header(req: Request, call_next):
    start_time = time.time()
    response = await call_next(req)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.get("/")
def index():
    return "Hello World\n"


@app.head("/v1/health")
async def health_check():
    return


class SearchRequest(BaseModel):
    query: str
    max_results: int = 10
    fetch_content: bool = False
    search_engines: list = ["duckduckgo"]

class SearchResponse(BaseModel):
    data: list[SearchResult]
    code: int
    message: str

@app.post("/v1/search", response_model=SearchResponse)
async def search(req: SearchRequest, _: dict = Depends(auth)):

    key = f"{req.query.strip()}{req.max_results}{req.fetch_content}{req.search_engines}"
    key = f"search_api.search.{hashlib.md5(key.encode()).hexdigest()}"
    cached = await redis_cli.get(key)
    if cached:
        logger.info(f"Cache hit for `{req.query}`")
        return {"data": json.loads(cached), "code": 0, "message": "success"}

    o = OmniSearchService(RequestsHtmlFetcher(), GPTClient(model_name=os.getenv("MODEL_NAME", "gpt-4o-mini")))

    for engine in req.search_engines:
        if engine == "google":
            google_config = SearchEngineConfig(
                api_key=os.getenv("GOOGLE_API_KEY"),
                params={"cx": os.getenv("GOOGLE_CX")}
            )
            o.add_engine("google", GoogleSearch(google_config))
        elif engine == "duckduckgo":
            duckduckgo_config = SearchEngineConfig(
                api_key="",
                params={"region": "cn-zh",}
            )
            o.add_engine("duckduckgo", DuckDuckGoSearch(duckduckgo_config))
        # elif engine == "bing":
        #     bing_config = SearchEngineConfig(
        #         api_key=os.getenv("BING_API_KEY")
        #     )
        #     o.add_engine("bing", BingSearch(bing_config))

    import time
    begin = time.time()
    logger.info(f"user query: `{req.query}`")
    results = await o.search(req.query.strip(), max_results=req.max_results, fetch_content=req.fetch_content)
    logger.info(f"total time elapsed: {time.time() - begin} s", )
    logger.info(f"search results count: {len(results)}")

    if len(results) > 0:
        json_data = json.dumps([result.model_dump() for result in results])
        await redis_cli.setex(key, int(os.environ.get("SEARCH_TTL", 30)), json_data)
    return {"data": results, "code": 0, "message": "success"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "0.0.0.0"), port=int(os.environ.get("PORT", 8000)))
