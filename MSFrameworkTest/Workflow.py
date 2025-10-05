import asyncio
from typing_extensions import Never
from agent_framework import WorkflowBuilder, WorkflowContext, WorkflowOutputEvent, executor


@executor(id="upper_case_executor")
async def to_upper_case(text: str, ctx: WorkflowContext[str]) -> None:
    """Transform the input to uppercase and forward it to the next step."""
    result = text.upper()

    # Send the intermediate result to the next executor
    await ctx.send_message(result)


@executor(id="reverse_text_executor")
async def reverse_text(text: str, ctx: WorkflowContext[Never, str]) -> None:
    """Reverse the input and yield the workflow output."""
    result = text[::-1]

    # Yield the final output for this workflow run
    await ctx.yield_output(result)


workflow = (
    WorkflowBuilder()
    .add_edge(to_upper_case, reverse_text)
    .set_start_executor(to_upper_case)
    .build()
)


async def main():
    # Run the workflow and stream events
    async for event in workflow.run_stream("hello world"):
        print(f"Event: {event}")
        if isinstance(event, WorkflowOutputEvent):
            print(f"Workflow completed with result: {event.data}")

if __name__ == "__main__":
    asyncio.run(main())
