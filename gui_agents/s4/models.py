from __future__ import annotations

from typing import Dict

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI


def build_chat_model(engine_params: Dict) -> BaseChatModel:
    """根据 engine 配置构建 LangChain ChatModel。"""

    if not engine_params:
        raise ValueError("engine_params 不能为空")

    engine_type = engine_params.get("engine_type", "openai")
    model_name = engine_params.get("model")
    api_key = engine_params.get("api_key")
    base_url = engine_params.get("base_url")
    temperature = engine_params.get("temperature")

    common_kwargs = {"model": model_name, "temperature": temperature}

    if engine_type == "openai":
        return ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            **{k: v for k, v in common_kwargs.items() if v is not None},
        )
    if engine_type == "anthropic":
        return ChatAnthropic(api_key=api_key, **common_kwargs)
    if engine_type in {"gemini", "google"}:
        return ChatGoogleGenerativeAI(
            api_key=api_key,
            **{k: v for k, v in common_kwargs.items() if v is not None},
        )

    raise ValueError(f"暂不支持的 engine_type: {engine_type}")

