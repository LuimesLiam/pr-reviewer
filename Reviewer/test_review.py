import httpx
import json

URL = "http://localhost:8001/review/stream"
payload = {
    "pr_number": 2,  # Replace with a valid PR number for your repo
    "repo_name": "LuimesLiam/HomeApp"  # Replace with the actual repository name
}
timeout = 120.0  # seconds


def main():
    review_comments = []  # Collect parsed review comments
    with httpx.Client(timeout=timeout) as client:
        # Tell httpx we want to stream the response
        with client.stream("POST", URL, json=payload) as response:
            print("Status:", response.status_code)
            if response.status_code != 200:
                print("Error:", response.text)
                return

            # Read line by line
            for raw_line in response.iter_lines():
                if not raw_line:
                    continue
                if isinstance(raw_line, bytes):
                    line = raw_line.decode("utf-8").strip()
                else:
                    line = raw_line.strip()
                # SSE frames come as "data: …
                if line.startswith("data:"):
                    # strip off the "data: " prefix
                    sse_payload = line[len("data:"):].strip()
                    try:
                        comment_obj = json.loads(sse_payload)
                        review_comments.append(comment_obj['review_comments'])
                    except Exception:
                        # Not a JSON payload, print as is
                        print("→", sse_payload)
                else:
                    print(line)
    # Print all attributes from each review comment
    print("\nParsed Review Comments:")
# later, to read them:
    for c in review_comments[0]:
        # now each `c` is a dict:
        print(c["file_name"], "needs rework?", c["requires_rework"])


if __name__ == "__main__":
    main()
