from MSAFAgent.Agent_framework_agent import ReviewerHandlerAgent
import asyncio
import functools
import json
from fastapi import FastAPI, HTTPException, Request, Response, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import httpx
from contextlib import asynccontextmanager, suppress
from dotenv import load_dotenv
from pydantic import BaseModel
from Agents.agent import ReviewerHandler
from Models.State import State
httpx_client: httpx.AsyncClient | None = None

origins = [
    "*"
]

HEARTBEAT_INTERVAL_SECONDS = 25


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup Happens Before Yield
    load_dotenv()

    httpx_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30))

    global agent_handler
    agent_handler = ReviewerHandler()
    await agent_handler.async_init()

    yield
    await httpx_client.aclose()
    # Cleanup Happens After Yield

app = FastAPI(lifespan=lifespan)


class CancelOnDisconnectMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # only care about HTTP
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        cancel_event = asyncio.Event()
        orig_receive = receive

        async def receive_wrapper():
            message = await orig_receive()
            if message["type"] == "http.disconnect":
                # client hung up
                print("Disconnect event detected")
                cancel_event.set()
            return message

        # attach both the wrapped receive and our event to the scope
        scope["receive"] = receive_wrapper
        scope["cancel_event"] = cancel_event

        # now hand off to the rest of the app
        return await self.app(scope, receive_wrapper, send)


app.add_middleware(CancelOnDisconnectMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def cancellable(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # locate the Request
        request: Request = kwargs.get("request") or next(
            a for a in args if isinstance(a, Request)
        )
        cancel_event: asyncio.Event = request.scope["cancel_event"]

        # now that body is already consumed, safely start watching
        orig_receive = request._receive

        async def watch_disconnect():
            try:
                while True:
                    msg = await orig_receive()
                    if msg["type"] == "http.disconnect":
                        cancel_event.set()
                        return
            except asyncio.CancelledError:
                pass

        watcher = asyncio.create_task(watch_disconnect())

        try:
            main_task = asyncio.create_task(func(*args, **kwargs))
            cancel_wait = asyncio.create_task(cancel_event.wait())
            done, _ = await asyncio.wait(
                {main_task, cancel_wait}, return_when=asyncio.FIRST_COMPLETED
            )
            if cancel_wait in done:
                main_task.cancel()
                with suppress(asyncio.CancelledError):
                    await main_task
                raise HTTPException(499, "Client disconnected")
            cancel_wait.cancel()
            return await main_task
        finally:
            watcher.cancel()

    return wrapper


class MessageBody(BaseModel):
    pr_number: int
    repo_name: str


# --- inside /review/stream ----------------------------------------------------
@app.post("/review/stream")
async def process_review_stream(body: MessageBody, request: Request):
    queue: asyncio.Queue[str] = asyncio.Queue()

    async def event_generator():
        run_task = asyncio.create_task(
            agent_handler.run(
                repo_name=body.repo_name,
                pr_number=body.pr_number,
                event_queue=queue,
            )
        )
        completed = False  # tracks whether we already sent a completion frame
        try:
            while True:
                # Wait for next queue item with heartbeat timeout
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL_SECONDS)
                    queue.task_done()
                except asyncio.TimeoutError:
                    # Heartbeat
                    yield "data: {\"type\":\"heartbeat\"}\n\n"
                    # If the background task is finished (success or error) and there are no more messages, finalize.
                    if run_task.done() and queue.empty() and not completed:
                        completed = True
                        try:
                            result = await run_task
                            # Normal path if graph finished without sending __COMPLETE__ (e.g. crash before completion node)
                            if isinstance(result, dict):
                                rc = result.get("review_comments", [])
                            else:
                                rc = []
                            payload = {"type": "complete",
                                       "review_comments": rc, "forced": True}
                            yield f"data: {json.dumps(payload)}\n\n"
                        except Exception as e:
                            err_payload = {
                                "type": "error", "message": f"Background task failed: {str(e)}"}
                            yield f"data: {json.dumps(err_payload)}\n\n"
                        break
                    continue

                # Handle queue message
                if msg == "__COMPLETE__":
                    # Normal completion path
                    try:
                        result = await run_task
                        if type(result) is State:
                            final_state: State = result
                        elif isinstance(result, dict):
                            final_state: State = State(**result)
                        else:
                            raise HTTPException(
                                status_code=500, detail="Invalid State result type")
                        payload = {
                            "type": "complete",
                            "review_comments": final_state["review_comments"],
                        }
                        yield f"data: {json.dumps(payload)}\n\n"
                    except Exception as e:
                        err_payload = {"type": "error",
                                       "message": f"Completion error: {str(e)}"}
                        yield f"data: {json.dumps(err_payload)}\n\n"
                    completed = True
                    break

                # Normal progress messages
                try:
                    data = json.loads(msg)
                    yield f"data: {json.dumps(data)}\n\n"
                except Exception:
                    yield f"data: {msg}\n\n"

                # If background task has ended (unexpectedly) and no formal completion was sent, force completion
                if run_task.done() and not completed and queue.empty():
                    try:
                        result = await run_task
                        if isinstance(result, dict):
                            rc = result.get("review_comments", [])
                        else:
                            rc = []
                        payload = {"type": "complete",
                                   "review_comments": rc, "forced": True}
                        yield f"data: {json.dumps(payload)}\n\n"
                    except Exception as e:
                        err_payload = {
                            "type": "error", "message": f"Background task failed: {str(e)}"}
                        yield f"data: {json.dumps(err_payload)}\n\n"
                    completed = True
                    break
        finally:
            if not run_task.done():
                run_task.cancel()
                with suppress(asyncio.CancelledError):
                    await run_task

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Example Usage ---

@app.post("/review/test")
async def test():
    """Example usage of the reviewer workflow, streaming events as they occur."""
    handler = ReviewerHandlerAgent()

    async def event_generator():
        async for event in await handler.run(
            repo_name="LuimesLiam/HomeApp",  # Replace with actual repo
            pr_number=1  # Replace with actual PR number
        ):
            # You may want to format the event as JSON or string, depending on your event type
            import json
            try:
                yield f"data: {json.dumps(event)}\n\n"
            except Exception:
                yield f"data: {str(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    asyncio.run(test())

    # result_state = None
    # async for event in workflow.run_stream(initial_state):
    #     logger.debug(f"Workflow event: {type(event).__name__}")
    #     print(f"Event: {event}")
    #     if isinstance(event, WorkflowOutputEvent):
    #         result_state = event.data
