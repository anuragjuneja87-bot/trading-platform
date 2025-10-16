"""
backend/monitors/__init__.py
Monitors package for specialized news/event monitoring
"""

from .openai_news_monitor import OpenAINewsMonitor

__all__ = ['OpenAINewsMonitor']