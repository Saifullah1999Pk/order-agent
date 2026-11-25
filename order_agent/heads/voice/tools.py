"""Pipecat tool schemas for the voice head, built from the Controller's framework-free specs."""

from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema
from pipecat.frames.frames import FunctionCallResultProperties

from order_agent.controller.session import CallController
from order_agent.controller.toolspecs import ToolSpec
from order_agent.controller.tools import ToolOutcome


def _handler(controller: CallController, spec: ToolSpec):
    async def handler(params):
        sent = False

        async def send(outcome: ToolOutcome) -> None:
            nonlocal sent
            sent = True  # set first: a failing callback must not be retried into a second reply
            # A successful end_call must not trigger another inference (a second goodbye racing
            # the pipeline end). A refusal and every other tool still let the LLM respond.
            properties = None if outcome.run_llm else FunctionCallResultProperties(run_llm=False)
            await params.result_callback(outcome.as_payload(), properties=properties)

        outcome = await controller.perform(spec.name, params.arguments, reply=send)
        if not sent:
            await send(outcome)  # the controller replies itself only on a successful end_call

    return handler


def build_tools(controller: CallController) -> ToolsSchema:
    return ToolsSchema(
        standard_tools=[
            FunctionSchema(
                name=spec.name,
                description=spec.description,
                properties=spec.properties,
                required=spec.required,
                handler=_handler(controller, spec),
            )
            for spec in controller.tool_specs()
        ]
    )
