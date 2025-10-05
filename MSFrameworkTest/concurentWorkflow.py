import asyncio
import random
from pydantic import BaseModel
from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential
from agent_framework.openai import OpenAIChatClient
import os
from agent_framework import ChatAgent
from agent_framework import AgentRunResponse
from agent_framework import Executor, WorkflowBuilder, WorkflowContext, WorkflowOutputEvent, handler
from typing_extensions import Never
from agent_framework import WorkflowBuilder, WorkflowViz


class PersonInfo(BaseModel):
    """Information about a person."""
    name: str | None = None
    age: int | None = None
    occupation: str | None = None


class Model:
    def __init__(self):
        self.chat_client = OpenAIChatClient(
            api_key=os.environ["GEMINI_API_KEY"],
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            model_id="gemini-2.5-flash"
        )
        self.agent = ChatAgent(
            chat_client=self.chat_client,
            name="HelpfulAssistant",
            instructions="You are a helpful assistant that extracts person information from text."
        )


class BaseModelExecutor(Executor):
    """Base executor that initializes and shares the model instance."""

    def __init__(self, id: str, model: Model):
        super().__init__(id=id)
        self.model = model


class Dispatcher(BaseModelExecutor):
    """
    The sole purpose of this executor is to dispatch the input of the workflow to
    other executors.
    """
    @handler
    async def handle(self, numbers: list[int], ctx: WorkflowContext[list[int]]):
        if not numbers:
            raise RuntimeError("Input must be a valid list of integers.")
        await ctx.send_message(numbers)


class Average(BaseModelExecutor):
    """Calculate the average of a list of integers."""
    @handler
    async def handle(self, numbers: list[int], ctx: WorkflowContext[float]):
        average: float = sum(numbers) / len(numbers)
        result = await self.model.agent.run(
            "John Smith is 35 and works as a software engineer.",
            response_format=PersonInfo
        )
        print(result)
        await ctx.set_shared_state("person_info", result)
        await ctx.send_message(average)


class Sum(BaseModelExecutor):
    """Calculate the sum of a list of integers."""
    @handler
    async def handle(self, numbers: list[int], ctx: WorkflowContext[int]):
        total: int = sum(numbers)
        await ctx.send_message(total)


class Aggregator(BaseModelExecutor):
    """Aggregate the results from the different tasks and yield the final output."""
    @handler
    async def handle(self, results: list[int | float], ctx: WorkflowContext[Never, list[int | float]]):
        person_info: PersonInfo | None = await ctx.get_shared_state("person_info")
        await ctx.yield_output(results)


async def main() -> None:
    # Instantiate the model once
    model = Model()
    # 1) Create the executors, injecting the shared model
    dispatcher = Dispatcher(id="dispatcher", model=model)
    average = Average(id="average", model=model)
    summation = Sum(id="summation", model=model)
    aggregator = Aggregator(id="aggregator", model=model)

    # 2) Build a simple fan out and fan in workflow
    workflow = (
        WorkflowBuilder()
        .set_start_executor(dispatcher)
        .add_fan_out_edges(dispatcher, [average, summation])
        .add_fan_in_edges([average, summation], aggregator)
        .build()
    )

    # viz = WorkflowViz(workflow)
    # mermaid_content = viz.to_mermaid()
    # print("Mermaid flowchart:")
    # print(mermaid_content)

    # try:
    #     # Export as SVG (vector format, recommended)
    #     svg_file = viz.export(format="svg")
    #     print(f"SVG exported to: {svg_file}")

    #     # Export as PNG (raster format)
    #     png_file = viz.export(format="png")
    #     print(f"PNG exported to: {png_file}")

    #     # Export as PDF (vector format)
    #     pdf_file = viz.export(format="pdf")
    #     print(f"PDF exported to: {pdf_file}")

    #     # Export raw DOT file
    #     dot_file = viz.export(format="dot")
    #     print(f"DOT file exported to: {dot_file}")

    # except ImportError:
    #     print("Install 'viz' extra and GraphViz for image export:")
    #     print("pip install agent-framework[viz]")
    #     print("Also install GraphViz binaries for your platform")

    # 3) Run the workflow
    output: list[int | float] | None = None
    async for event in workflow.run_stream([random.randint(1, 100) for _ in range(10)]):
        print(f"Event: {event}")
        if isinstance(event, WorkflowOutputEvent):
            output = event.data

    if output is not None:
        print(output)

if __name__ == "__main__":
    asyncio.run(main())
