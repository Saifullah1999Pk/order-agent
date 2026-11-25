"""Maps each Pipecat event to one CallController call. No state and no decisions live here."""

from loguru import logger

from order_agent.controller import CallController


def register_events(transport, user_aggregator, assistant_aggregator, llm, controller: CallController, runner) -> None:
    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Client connected")
        controller.channel_opened()

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Client disconnected")
        await controller.drop()
        await runner.cancel()

    @user_aggregator.event_handler("on_user_turn_started")
    async def on_user_turn_started(aggregator, strategy):
        controller.restaurant_spoke()

    @user_aggregator.event_handler("on_user_turn_message_added")
    async def on_user_turn(aggregator, message):
        logger.info(f"Transcript restaurant: {message.content}")
        controller.add_line("restaurant", message.content)

    @llm.event_handler("on_function_calls_started")
    async def on_function_calls_started(service, function_calls):
        controller.function_calls_started()

    @assistant_aggregator.event_handler("on_assistant_turn_started")
    async def on_assistant_turn_started(aggregator):
        controller.llm_turn_started()

    @assistant_aggregator.event_handler("on_assistant_turn_stopped")
    async def on_assistant_turn(aggregator, message):
        logger.info(f"Transcript agent: {message.content}")
        controller.llm_turn_ended(message.content, message.interrupted)
