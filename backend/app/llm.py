from functools import lru_cache

from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI, OpenAIEmbeddings

from .config import get_settings

GROQ_BASE_URL = "https://api.groq.com/openai/v1"


@lru_cache
def get_llm():
    s = get_settings()
    if s.llm_provider == "azure":
        return AzureChatOpenAI(
            azure_endpoint=s.azure_openai_endpoint,
            api_key=s.azure_openai_api_key,
            api_version=s.azure_openai_api_version,
            azure_deployment=s.azure_openai_chat_deployment,
        )
    if s.llm_provider == "groq":
        return ChatOpenAI(
            api_key=s.groq_api_key,
            model=s.groq_chat_model,
            base_url=GROQ_BASE_URL,
            max_retries=3,
        )
    return ChatOpenAI(api_key=s.openai_api_key, model=s.openai_chat_model)


@lru_cache
def get_embeddings():
    s = get_settings()
    if s.llm_provider == "azure":
        return AzureOpenAIEmbeddings(
            azure_endpoint=s.azure_openai_endpoint,
            api_key=s.azure_openai_api_key,
            api_version=s.azure_openai_api_version,
            azure_deployment=s.azure_openai_embedding_deployment,
        )
    if s.llm_provider == "groq":
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

        return FastEmbedEmbeddings(model_name=s.embedding_model)
    return OpenAIEmbeddings(api_key=s.openai_api_key, model=s.openai_embedding_model)
