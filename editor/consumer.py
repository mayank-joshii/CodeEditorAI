import os
import json
import uuid
import asyncio
import urllib.parse
from channels.generic.websocket import AsyncWebsocketConsumer
from docker import from_env as docker_from_env

# Import your OpenAI client as you do in views
from editor.views import OpenAI

# Initialize your OpenAI client with your base_url and api_key
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

class CodeRunConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.docker_client = docker_from_env()
        self.container = None
        self.socket = None
        self.output_task = None

    async def disconnect(self, close_code):
        if self.output_task:
            self.output_task.cancel()
        if self.socket:
            self.socket.close()
        if self.container:
            self.container.remove(force=True)

    async def receive(self, text_data):
        data = json.loads(text_data)

        if "code" in data and "input" in data:
            code = data["code"]
            user_input = data["input"]

            run_id = str(uuid.uuid4())
            temp_dir = os.path.join(os.getcwd(), "temp_runs", run_id)
            os.makedirs(temp_dir, exist_ok=True)

            # Write user code to user_code.py
            user_code_path = os.path.join(temp_dir, "user_code.py")
            with open(user_code_path, "w") as f:
                f.write(code)

            # Run container with user_code.py
            self.container = self.docker_client.containers.run(
                image="python-runner",
                volumes={temp_dir: {"bind": "/app", "mode": "rw"}},
                working_dir="/app",
                command=["python", "user_code.py"],
                stdin_open=True,
                tty=True,
                detach=True,
            )

            self.socket = self.container.attach_socket(
                params={'stdin': 1, 'stdout': 1, 'stderr': 1, 'stream': 1}
            )

            self.output_task = asyncio.create_task(self.stream_output())

            for line in user_input.splitlines():
                await self.send_input(line)

            # After container starts, generate AI explanation and Python Tutor URL
            ai_explanation = await self.get_ai_explanation(code)
            await self.send(text_data=json.dumps({
                "type": "ai_explanation",
                "content": ai_explanation
            }))

            python_tutor_url = self.get_python_tutor_visual(code)
            await self.send(text_data=json.dumps({
                "type": "python_tutor_visual",
                "content": python_tutor_url
            }))

        elif "input" in data:
            await self.send_input(data["input"])

    async def send_input(self, input_line):
        to_send = (input_line + "\n").encode('utf-8')
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.socket.send, to_send)

    async def stream_output(self):
        loop = asyncio.get_running_loop()
        try:
            while True:
                output = await loop.run_in_executor(None, self.socket.recv, 1024)
                if not output:
                    break
                decoded = output.decode('utf-8', errors='ignore')
                await self.send(text_data=json.dumps({"type": "output", "output": decoded}))
        except asyncio.CancelledError:
            pass

    async def get_ai_explanation(self, code):
        prompt = f"Explain this Python code in simple terms:\n\n{code}\n\nExplanation:"
        try:
            # openrouter.ai's OpenAI client usage — assuming async await possible, else wrap sync call in asyncio.to_thread
            completion = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.5,
            )
            explanation = completion.choices[0].message.content.strip()
            return explanation
        except Exception as e:
            return f"Error generating explanation: {str(e)}"

    def get_python_tutor_visual(self, code):
        base_url = "https://pythontutor.com/iframe-embed.html"
        params = {
            "code": code,
            "heapPrimitives": "false",
            "mode": "display",
            "origin": "opt-frontend.js",
            "py": "3",
            "rawInputLstJSON": "[]"
        }
        query_string = urllib.parse.urlencode(params)
        embed_url = f"{base_url}#{query_string}"
        return embed_url
