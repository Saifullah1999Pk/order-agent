"""The order agent: a voice bot that phones a restaurant as the customer.

Local Whisper STT -> Gemini LLM (with order tools) -> local Kokoro TTS.

Run from the order-agent folder:
    PYTHONIOENCODING=utf-8 uv run python bot.py
Then open http://localhost:7860/client/ and click Connect (you play the restaurant).
"""

import asyncio
from datetime import datetime

from loguru import logger

from order_agent.brief import load_brief
from order_agent.call import (
    NUDGE_TEXT,
    CallState,
    NudgeScheduler,
    NudgeTracker,
    make_on_end,
)
from order_agent.config import load_settings, pick_model
from order_agent.heads.voice.llm_factory import build_bot_llm
from order_agent.heads.voice.probe import make_probe
from order_agent.prompt import build_system_prompt
from order_agent.tools import build_tools
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.evals.transport import EvalTransportParams
from pipecat.frames.frames import EndWorkerFrame, LLMRunFrame
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
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import Model, WhisperSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

OPENING_WAIT_SECS = 3.0

transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    "eval": lambda: EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting bot")
    settings = load_settings()
    brief = load_brief(settings.brief_path)
    if settings.call_time:
        brief = brief.model_copy(update={"call_time": settings.call_time})
    if settings.llm_provider == "groq":
        model = settings.groq_model  # no Gemini probe: Gemini is not used
    elif settings.llm_provider == "ollama":
        model = settings.ollama_model  # local server: no probe, no key
    else:
        model = await pick_model(settings, make_probe(settings))
    logger.info(f"Using {settings.llm_provider} model {model}")

    call_state = CallState(brief, settings, datetime.now())

    # 1. Ears: speech -> text, locally. "base" + int8 keeps CPU latency low.
    stt = WhisperSTTService(
        device="cpu",
        compute_type="int8",
        settings=WhisperSTTService.Settings(model=Model.BASE.value),
    )

    # 2. Brain: text -> text (and tool calls), via a free tier (Gemini by default, Groq optional).
    llm = build_bot_llm(settings, build_system_prompt(brief), gemini_model=model)

    # 3. Mouth: text -> speech, locally (model files auto-download on first run).
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice="af_heart"))

    # Downstream, so the frames queued ahead (the goodbye) are flushed first.
    nudge_scheduler: NudgeScheduler | None = None

    async def push_end():
        if nudge_scheduler:
            nudge_scheduler.cancel()  # no nudge after end_call
        await llm.push_frame(EndWorkerFrame())

    on_end = make_on_end(call_state, push_end)

    # Handlers on the FunctionSchemas are registered automatically from the context's tools.
    context = LLMContext(tools=build_tools(call_state.session, on_end))
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(vad_analyzer=SileroVADAnalyzer()),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
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

    restaurant_spoke = False
    nudger = NudgeTracker()
    opening_task: asyncio.Task | None = None

    async def open_call_if_silent():
        await asyncio.sleep(OPENING_WAIT_SECS)
        if restaurant_spoke:
            return  # the normal turn flow answers them
        context.add_message(
            {
                "role": "developer",
                "content": "Nobody has spoken yet. Open the call: greet, say you'd like to place a delivery order.",
            }
        )
        await worker.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        nonlocal opening_task
        logger.info("Client connected")
        opening_task = asyncio.create_task(open_call_if_silent())

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        if opening_task:
            opening_task.cancel()
        nudge_scheduler.cancel()
        await call_state.on_disconnect()
        await runner.cancel()

    @user_aggregator.event_handler("on_user_turn_started")
    async def on_user_turn_started(aggregator, strategy):
        nonlocal restaurant_spoke
        restaurant_spoke = True
        nudger.on_user_turn_started()
        nudge_scheduler.cancel()

    @user_aggregator.event_handler("on_user_turn_message_added")
    async def on_user_turn(aggregator, message: UserTurnMessageAddedMessage):
        logger.info(f"Transcript restaurant: {message.content}")
        call_state.add_line("restaurant", message.content)

    @llm.event_handler("on_function_calls_started")
    async def on_function_calls_started(service, function_calls):
        nudger.on_function_call()

    @assistant_aggregator.event_handler("on_assistant_turn_started")
    async def on_assistant_turn_started(aggregator):
        nudger.on_llm_run_started()
        nudge_scheduler.cancel()

    async def fire_nudge():
        # Runs after a pause so the nudge does not land in the same per-minute quota window.
        context.add_message({"role": "developer", "content": NUDGE_TEXT})
        await worker.queue_frames([LLMRunFrame()])

    nudge_scheduler = NudgeScheduler(fire_nudge)

    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn(aggregator, message: AssistantTurnStoppedMessage):
        logger.info(f"Transcript agent: {message.content}")
        if message.content.strip():
            call_state.add_line("agent", message.content)
        if nudger.on_assistant_turn(message.content, interrupted=message.interrupted):
            logger.warning("Empty assistant turn, nudging the LLM")
            nudge_scheduler.schedule()

    await runner.run()
    nudge_scheduler.cancel()
    # Idle timeout or any other end without end_call: still write a report (no-op if one exists).
    await call_state.on_disconnect()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)


if __name__ == "__main__":
    from pipecat.runner.run import main

    main()
