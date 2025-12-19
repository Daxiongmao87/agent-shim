import subprocess
import shlex
import time
import uuid
import os
import tempfile
import logging
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

# ==========================================
# CONFIGURATION
# ==========================================

# The IP and Port to serve the API on
HOST = "127.0.0.1"
PORT = 8001

# THE COMMAND TEMPLATE
# Use {prompt} where the user message should go.
# Use {system} where the system message should go (if your CLI supports passing it as text).
# Use {system_file} if your CLI needs the system prompt in a temporary file (path will be injected).
# Example for 'qwen': 'qwen code -y "{prompt}"'
# Example for a tool taking stdin: 'my-tool' (and logic below would need piping, currently this setup favors arg-based CLIs)

COMMAND_TEMPLATE = 'qwen {prompt}'

# If true, the server will log the exact command being executed to the console.
DEBUG_MODE = True

# ==========================================
# APP SETUP
# ==========================================

app = FastAPI(title="CLI to OpenAI Proxy")
logger = logging.getLogger("uvicorn")

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str = "cli-agent"
    messages: List[Message]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False

# ==========================================
# CORE LOGIC
# ==========================================

def execute_cli_command(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Constructs the shell command, executes it, and returns the stdout.
    """
    
    # 1. Handle System Prompt File (if the template uses {system_file})
    temp_system_file = None
    system_file_path = ""
    
    if "{system_file}" in COMMAND_TEMPLATE and system_prompt:
        temp_system_file = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix=".txt")
        temp_system_file.write(system_prompt)
        temp_system_file.flush()
        temp_system_file.close()
        system_file_path = temp_system_file.name
    
    # 2. Prepare Variables for formatting
    # We use shlex.quote to ensure the prompt doesn't break out of the shell command
    safe_prompt = shlex.quote(prompt)
    safe_system = shlex.quote(system_prompt if system_prompt else "")
    safe_system_path = shlex.quote(system_file_path)
    
    # 3. Format the command
    # If the template does NOT use {system} or {system_file}, we might want to prepend 
    # the system prompt to the user prompt if it exists.
    final_command = COMMAND_TEMPLATE
    
    # Simple logic: If template has explicit placeholder, use it. 
    # Otherwise, if system prompt exists, prepend it to prompt content effectively.
    if "{system}" in COMMAND_TEMPLATE:
        final_command = final_command.format(prompt=safe_prompt, system=safe_system, system_file=safe_system_path)
    elif "{system_file}" in COMMAND_TEMPLATE:
        final_command = final_command.format(prompt=safe_prompt, system=safe_system, system_file=safe_system_path)
    else:
        # Fallback: Prepend system prompt to user prompt if script doesn't handle it explicitly
        if system_prompt:
            combined = f"System: {system_prompt}\nUser: {prompt}"
            final_command = final_command.format(prompt=shlex.quote(combined))
        else:
            final_command = final_command.format(prompt=safe_prompt)

    if DEBUG_MODE:
        logger.info(f"Executing: {final_command}")

    # 4. Execute
    try:
        # We run with shell=True to allow the template to be flexible (e.g. pipes, flags)
        # Note: shlex.quote above mitigates injection, but this is a dev tool, so caution is advised.
        result = subprocess.run(
            final_command, 
            shell=True, 
            capture_output=True, 
            text=True
        )
        
        # Cleanup temp file
        if temp_system_file and os.path.exists(system_file_path):
            os.remove(system_file_path)

        if result.returncode != 0:
            logger.error(f"CLI Error Stderr: {result.stderr}")
            return f"Error executing CLI agent:\n{result.stderr}"
            
        return result.stdout.strip()

    except Exception as e:
        logger.error(f"Execution Exception: {str(e)}")
        if temp_system_file and os.path.exists(system_file_path):
            os.remove(system_file_path)
        return f"Proxy Error: {str(e)}"

# ==========================================
# ENDPOINTS
# ==========================================

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible endpoint.
    """
    
    # 1. Parse Messages
    # CLI agents usually just want the "task". We will look for the last user message.
    # Optionally, we can concatenate the whole history, but for 'qwen code' style tools,
    # usually the immediate prompt is what matters.
    
    system_prompt = None
    user_prompt = ""
    
    # Simple extraction strategy:
    # - Find first system message
    # - Find last user message
    # (You can modify this to concatenate all history if your CLI supports context)
    
    for msg in request.messages:
        if msg.role == "system":
            system_prompt = msg.content
    
    # Get last message that isn't system (usually user)
    # If there are multiple user messages, this basic MVP takes the last one.
    # To support history, you'd concatenate them here.
    relevant_msgs = [m for m in request.messages if m.role == "user"]
    if relevant_msgs:
        user_prompt = relevant_msgs[-1].content
    else:
        # Fallback if no user message found (rare)
        user_prompt = "Hello"

    # 2. Execute CLI
    response_text = execute_cli_command(user_prompt, system_prompt)
    
    # 3. Format OpenAI Response
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_text
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": len(user_prompt), # Dummy values
            "completion_tokens": len(response_text),
            "total_tokens": len(user_prompt) + len(response_text)
        }
    }

@app.get("/v1/models")
async def list_models():
    """
    Mock models endpoint so clients don't crash listing models.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "cli-agent",
                "object": "model",
                "created": int(time.time()),
                "owned_by": "user"
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    print(f"Starting CLI Proxy on http://{HOST}:{PORT}")
    print(f"Target Command Template: {COMMAND_TEMPLATE}")
    uvicorn.run(app, host=HOST, port=PORT)
