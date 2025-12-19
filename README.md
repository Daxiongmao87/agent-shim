# Agent Shim: CLI to OpenAI Proxy

Agent Shim is a lightweight FastAPI application that acts as a bridge between local CLI-based LLM agents (like `qwen`, `llm`, or custom scripts) and clients that expect the OpenAI API format.

This allows you to use your favorite local CLI tools with chat interfaces, IDE plugins, or other software designed for the OpenAI API.

## Features

- **OpenAI Compatible**: Exposes `/v1/chat/completions` and `/v1/models` endpoints.
- **Configurable Backend**: Easily wrap any CLI command using a simple template string.
- **Lightweight**: Built on FastAPI and standard Python libraries.

## Prerequisites

- Python 3.8+
- The CLI tool you intend to wrap (e.g., `qwen`, `ollama`, etc.) installed and accessible in your path.

## Installation

1.  **Clone the repository** (if you haven't already):
    ```bash
    git clone https://github.com/Daxiongmao87/agent-shim.git
    cd agent-shim
    ```

2.  **Create a virtual environment**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies**:
    ```bash
    pip install fastapi uvicorn
    ```

## Configuration

Open `app.py` and modify the `COMMAND_TEMPLATE` variable to match your CLI tool's syntax.

```python
# Example for 'qwen'
COMMAND_TEMPLATE = 'qwen {prompt}'

# Example for a tool that accepts a system prompt via a flag
# COMMAND_TEMPLATE = 'my-agent --system "{system}" --user "{prompt}"'
```

- `{prompt}`: Replaced with the user's last message.
- `{system}`: Replaced with the system prompt (if provided).
- `{system_file}`: If your tool reads system prompts from a file, use this. The app will create a temp file and inject the path here.

## Usage

1.  **Start the server**:
    ```bash
    python app.py
    ```
    The server will start on `http://127.0.0.1:8001`.

2.  **Test with curl**:
    ```bash
    curl http://127.0.0.1:8001/v1/chat/completions \
      -H "Content-Type: application/json" \
      -d '{
        "model": "cli-agent",
        "messages": [{"role": "user", "content": "Hello world"}]
      }'
    ```

3.  **Connect a Client**:
    Configure your OpenAI-compatible client (e.g., a chat UI) with:
    - **Base URL**: `http://127.0.0.1:8001/v1`
    - **API Key**: (Any string, e.g., `dummy`)

## Limitations

- **Streaming**: Response streaming is currently not supported. The full response is returned after the CLI command completes.
- **Context**: By default, this shim extracts the *last* user message and passes it to the CLI. It does not automatically maintain full conversation history unless your CLI tool handles state independently.

## License

[MIT](LICENSE)
