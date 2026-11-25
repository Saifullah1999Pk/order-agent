"""The voice head's CallHooks: the two things only the Pipecat pipeline can do."""

from pipecat.frames.frames import EndWorkerFrame, LLMRunFrame


class PipecatHooks:
    def __init__(self, context, worker, llm) -> None:
        self._context = context
        self._worker = worker
        self._llm = llm

    async def inject(self, text: str) -> None:
        self._context.add_message({"role": "developer", "content": text})
        await self._worker.queue_frames([LLMRunFrame()])

    async def hangup(self) -> None:
        # Pushed downstream from the LLM, so the frames queued ahead (the goodbye) are flushed first.
        await self._llm.push_frame(EndWorkerFrame())
