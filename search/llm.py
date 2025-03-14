import os
import abc
from openai import AsyncOpenAI

class LLMClient(abc.ABC):
    @abc.abstractmethod
    async def completion(self, messages: list):
        pass

    async def stream_completion(self, messages: list):
        pass


class GPTClient(LLMClient):
    def __init__(self, api_key: str = os.environ.get("OPENAI_API_KEY"), base_url: str = os.environ.get("OPENAI_BASE_URL"), model_name: str = os.environ.get("MODEL_NAME")):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model_name = model_name

    async def stream_completion(self, messages: list):
        return await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            stream=True,
            temperature=0.7
        )
    
    async def completion(self, messages: list):
        return await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=0.7
        )
