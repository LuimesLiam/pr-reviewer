import asyncio
import httpx
import json

URL = "http://0.0.0.0:8001/review/test"
payload = {
    "pr_number": 1,  # Replace with a valid PR number for your repo
    "repo_name": "LuimesLiam/HomeApp"  # Replace with the actual repository name
}
timeout = 120.0  # seconds


async def main():
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", URL, json=payload) as response:
            print("Status:", response.status_code)
            if response.status_code != 200:
                print("Error:", await response.aread())
                return

            # SSE: each event is a line starting with 'data: '
            async for raw_line in response.aiter_lines():
                if not raw_line:
                    continue
                line = raw_line.strip()
                if line.startswith("data:"):
                    sse_payload = line[len("data:"):].strip()
                    try:
                        event = json.loads(sse_payload)
                        print(f"Event: {event}")
                        if event.get("type") == "complete":
                            print(f"Workflow completed with result: {event}")
                    except Exception:
                        print("→", sse_payload)
                else:
                    print(line)

if __name__ == "__main__":
    asyncio.run(main())
