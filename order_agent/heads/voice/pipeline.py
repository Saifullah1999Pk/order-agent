"""The voice head's pipeline: Pipecat STT -> LLM -> TTS wired onto a CallController.

Local Whisper STT -> Gemini LLM (with order tools) -> local Kokoro TTS.
"""

from loguru import logger

from order_agent.config import Settings, load_settings, pick_model
from order_agent.controller import CallController
from order_agent.heads.voice.bridge import register_events
from order_agent.heads.voice.hooks import PipecatHooks
from order_agent.heads.voice.llm_factory import build_bot_llm
from order_agent.heads.voice.probe import make_probe
from order_agent.heads.voice.tools import build_tools
from order_agent.model.brief import OrderBrief, load_brief
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.evals.transport import EvalTransportParams
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker, ProcessorUnusablePolicy
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.kokoro.tts import KokoroTTSService
from pipecat.services.whisper.stt import Model, WhisperSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.workers.runner import WorkerRunner

transport_params = {
    "webrtc": lambda: TransportParams(audio_in_enabled=True, audio_out_enabled=True),
    "eval": lambda: EvalTransportParams(audio_in_enabled=True, audio_out_enabled=True),
}


def load_call_inputs() -> tuple[Settings, OrderBrief]:
    """Settings from .env / the environment, and the brief with the ORDER_CALL_TIME override applied."""
    settings = load_settings()
    brief = load_brief(settings.brief_path)
    if settings.call_time:
        brief = brief.model_copy(update={"call_time": settings.call_time})
    return settings, brief


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting bot")
    settings, brief = load_call_inputs()
    if settings.llm_provider == "groq":
        model = settings.groq_model  # no Gemini probe: Gemini is not used
    elif settings.llm_provider == "ollama":
        model = settings.ollama_model  # local server: no probe, no key
    else:
        model = await pick_model(settings, make_probe(settings))
    logger.info(f"Using {settings.llm_provider} model {model}")

    # Created first, without hooks: the tools need it, and the hooks need objects built below.
    controller = CallController(brief, reports_dir=settings.reports_dir)

    # 1. Ears: speech -> text, locally. "base" + int8 keeps CPU latency low.
    stt = WhisperSTTService(
        device="cpu",
        compute_type="int8",
        settings=WhisperSTTService.Settings(model=Model.BASE.value),
    )

    # 2. Brain: text -> text (and tool calls), via a free tier (Gemini by default, Groq optional).
    llm = build_bot_llm(settings, controller.instructions, gemini_model=model)

    # 3. Mouth: text -> speech, locally (model files auto-download on first run).
    tts = KokoroTTSService(settings=KokoroTTSService.Settings(voice="af_heart"))

    # Handlers on the FunctionSchemas are registered automatically from the context's tools.
    context = LLMContext(tools=build_tools(controller))
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

    # Attached before the events are registered and before runner.run(), so before the transport
    # can connect: the opening timer, nudges and hangup are all live from the first event.
    controller.attach_hooks(PipecatHooks(context, worker, llm))
    register_events(transport, user_aggregator, assistant_aggregator, llm, controller, runner)

    await runner.run()
    # Idle timeout or any other end without end_call: still write a report (no-op if one exists).
    await controller.drop()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)
