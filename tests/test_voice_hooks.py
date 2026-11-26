"""T026: PipecatHooks implements CallHooks over the Pipecat context, worker and LLM."""

from pipecat.frames.frames import EndWorkerFrame, LLMRunFrame

from order_agent.heads.voice.hooks import PipecatHooks


class FakeContext:
    def __init__(self):
        self.messages = []

    def add_message(self, message):
        self.messages.append(message)


class FakeWorker:
    def __init__(self, log):
        self.log = log

    async def queue_frames(self, frames):
        self.log.append(("queue_frames", list(frames)))


class FakeLLM:
    def __init__(self):
        self.pushed = []

    async def push_frame(self, frame, *args, **kwargs):
        self.pushed.append(frame)


async def test_inject_adds_developer_message_then_runs_the_llm():
    context, log = FakeContext(), []
    context.add_message = lambda m: log.append(("add_message", m))
    hooks = PipecatHooks(context, FakeWorker(log), FakeLLM())
    await hooks.inject("x")
    assert log[0] == ("add_message", {"role": "developer", "content": "x"})
    assert log[1][0] == "queue_frames" and len(log[1][1]) == 1
    assert isinstance(log[1][1][0], LLMRunFrame)
    assert len(log) == 2


async def test_hangup_pushes_end_worker_frame_through_the_llm():
    llm = FakeLLM()
    hooks = PipecatHooks(FakeContext(), FakeWorker([]), llm)
    await hooks.hangup()
    assert len(llm.pushed) == 1 and isinstance(llm.pushed[0], EndWorkerFrame)
