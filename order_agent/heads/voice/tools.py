"""Pipecat tool schemas for the voice head, built from the Controller's framework-free specs."""

from pipecat.adapters.llm.schemas.function_schema import FunctionSchema
from pipecat.adapters.llm.schemas.tools_schema import ToolsSchema

from order_agent.controller.session import CallController
from order_agent.controller.toolspecs import ToolSpec


def _handler(controller: CallController, spec: ToolSpec):
    async def handler(params):
        outcome = await controller.perform(spec.name, params.arguments)
        await params.result_callback(outcome.as_payload())

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
