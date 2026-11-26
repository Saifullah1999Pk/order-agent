"""The order agent: a voice bot that phones a restaurant as the customer.

Entry shim for the Pipecat runner; the pipeline lives in order_agent/heads/voice/pipeline.py.

Run from the order-agent folder:
    PYTHONIOENCODING=utf-8 uv run python bot.py
Then open http://localhost:7860/client/ and click Connect (you play the restaurant).
"""

from order_agent.heads.voice.pipeline import bot, run_bot, transport_params

__all__ = ["bot", "run_bot", "transport_params"]

if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
