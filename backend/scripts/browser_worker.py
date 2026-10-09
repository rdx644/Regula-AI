"""Synthetic extraction adapter for browser tests; never a model evaluation.

Requires ENVIRONMENT=test and only accepts the explicit E2E synthetic phrase.
Launch from backend with python -m scripts.browser_worker.
"""
import asyncio
import re
from app.core.config import settings
from app.core import ai_provider
from app.agents.schemas import ObligationExtractionBatch
from app.core.ai_provider import LLMResponse, ModelProvider
from app.services.queue import JobQueue, Worker


class BrowserFixtureProvider:
    async def complete(self, messages, response_model, config):
        if response_model is not ObligationExtractionBatch:
            raise RuntimeError("Browser adapter supports extraction fixtures only")
        prompt = messages[-1]['content']
        phrase = "The synthetic bank shall review its capital ratio daily."
        if phrase not in prompt:
            raise ValueError("Unrecognized browser fixture")
        result = response_model(obligations=[{
            'obligation_text': phrase, 'actor': 'synthetic bank',
            'requirement': 'review its capital ratio', 'frequency': 'daily',
            'source_text_snippet': phrase, 'confidence': .95,
            'reasoning': 'Deterministic browser fixture; no external model executed',
        }])
        return LLMResponse(result, '', 'browser-fixture-v1', 0, ModelProvider.FALLBACK)


async def main():
    if settings.ENVIRONMENT != 'test':
        raise RuntimeError("Browser adapter is restricted to ENVIRONMENT=test")
    ai_provider.OpenAIProvider = BrowserFixtureProvider
    from app.workers.handlers import get_handlers
    worker = Worker(JobQueue(), 'browser-fixture', get_handlers(), poll_interval=.1)
    await worker.start()
    print('browser-fixture-ready', flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await worker.stop()


if __name__ == '__main__':
    asyncio.run(main())
