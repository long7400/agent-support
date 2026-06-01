"""LangGraph tools for enhanced language model capabilities.

This package contains custom tools that can be used with LangGraph to extend
the capabilities of language models. Currently includes tools for web search
and other external integrations.
"""

from langchain_core.tools.base import BaseTool

from app.core.config import settings

from .ask_human import ask_human
from .duckduckgo_search import duckduckgo_search_tool

tools: list[BaseTool] = [ask_human]

if settings.WEB_SEARCH_ENABLED:
    tools.append(duckduckgo_search_tool)
