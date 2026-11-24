"""A zero-cost cascade voice agent: local Whisper STT -> Gemini LLM -> local Kokoro TTS.

Only the LLM step leaves your machine (Gemini free tier). Speech recognition and
speech synthesis run locally on the CPU.

Run from c:\\Users\\Saif\\Voice-Agent:
    PYTHONIOENCODING=utf-8 uv run --project pipecat python bots/free_voice_bot.py
Then open http://localhost:7860/client/ and click Connect.
"""

import asyncio

from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from order_agent.config import load_settings
from pipecat.evals.transport import EvalTransportParams
from pipecat.frames.frames import LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    AssistantTurnStoppedMessage,
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
    UserTurnMessageAddedMessage,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import Model, WhisperSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

# Only the browser (WebRTC) transport: no Daily/Twilio accounts needed.
transport_params = {
    "eval": lambda: EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True),
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting bot")

    # 1. Ears: speech -> text, locally. "base" + int8 keeps CPU latency low.
    stt = WhisperSTTService(
        device="cpu",
        compute_type="int8",
        settings=WhisperSTTService.Settings(model=Model.BASE.value),
    )

    # 2. Brain: text -> text, via Gemini free tier.
    llm = GoogleLLMService(
        api_key=load_settings().google_api_key,
        settings=GoogleLLMService.Settings(
            # Fastest model that answered on the free tier (2026-11-23 probe);
            # 3.8/3.7-flash were returning 503 "high demand" at the time.
            model="gemini-3.5-flash-lite",
            system_instruction=(
                "You are a customer phoning Karachi Kitchen to order 2 chicken biryani for delivery. "
                "Keep turns short: one or two plain sentences, no emojis or markdown."
            ),
        ),
    )

    # 3. Mouth: text -> speech, locally (model files auto-download on first run).
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice="af_heart"))

    # Conversation memory + turn detection (Silero VAD decides when you stopped talking).
    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),  # audio from your browser mic
            stt,  # audio -> text
            user_aggregator,  # add your words to the context
            llm,  # context -> reply text (streamed)
            tts,  # reply text -> audio (streamed)
            transport.output(),  # audio to your browser speaker
            assistant_aggregator,  # add the bot's spoken words to the context
        ]
    )

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
        processor_unusable_policy=ProcessorUnusablePolicy.END,
    )
    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")
        await asyncio.sleep(3)
        context.add_message({"role": "developer", "content": "Nobody has spoken yet. Open the call."})
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await runner.cancel()

    @user_aggregator.event_handler("on_user_turn_message_added")
    async def on_user_turn(aggregator, message: UserTurnMessageAddedMessage):
        logger.info(f"Transcript user: {message.content}")

    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn(aggregator, message: AssistantTurnStoppedMessage):
        logger.info(f"Transcript bot: {message.content}")

    await runner.run()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
