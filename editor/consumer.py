import os
import json
import uuid
import asyncio
import urllib.parse
import docker
from channels.generic.websocket import AsyncWebsocketConsumer
from editor.views import OpenAI

# Initialize OpenAI client (move the API key to .env or settings for security in production)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

class CodeRunConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        self.docker_client = docker.from_env()
        self.container = None
        self.output_task = None
        self.reading_task = None

    async def disconnect(self, close_code):
        if self.output_task:
            self.output_task.cancel()
            try:
                await self.output_task
            except asyncio.CancelledError:
                pass

        if self.reading_task:
            self.reading_task.cancel()
            try:
                await self.reading_task
            except asyncio.CancelledError:
                pass

        if self.container:
            try:
                self.container.kill()
                self.container.remove(force=True)
            except Exception:
                pass

    async def receive(self, text_data):
        data = json.loads(text_data)

        if "code" in data and "input" in data:
            code = data["code"]
            user_input = data["input"]

            run_id = str(uuid.uuid4())
            temp_dir = os.path.join(os.getcwd(), "temp_runs", run_id)
            os.makedirs(temp_dir, exist_ok=True)

            user_code_path = os.path.join(temp_dir, "user_code.py")
            with open(user_code_path, "w") as f:
                f.write(code)

            # Remove old container if exists
            if self.container:
                try:
                    self.container.kill()
                    self.container.remove(force=True)
                except Exception:
                    pass

            # Run code inside Docker container
            self.container = self.docker_client.containers.run(
                image="python-runner",
                volumes={temp_dir: {"bind": "/app", "mode": "rw"}},
                working_dir="/app",
                command=["python", "user_code.py"],
                stdin_open=True,
                tty=True,
                detach=True,
                stream=True,
            )

            # Stream container output
            self.output_task = asyncio.create_task(self.stream_container_logs())

            # Send user input to stdin
            for line in user_input.splitlines():
                await self.send_input(line)

            # AI Explanation
            explanation = await self.get_ai_explanation(code)
            await self.send(text_data=json.dumps({
                "type": "ai_explanation",
                "content": explanation
            }))

            # Python Tutor Visualization
            tutor_url = self.get_python_tutor_visual(code)
            await self.send(text_data=json.dumps({
                "type": "python_tutor_visual",
                "content": tutor_url
            }))

        elif "input" in data:
            await self.send_input(data["input"])

    async def send_input(self, input_line):
        if not self.container:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": "Container not running."
            }))
            return

        loop = asyncio.get_running_loop()
        try:
            exec_instance = self.docker_client.api.exec_create(
                container=self.container.id,
                cmd=["/bin/sh", "-c", f'echo "{input_line}" >> /dev/stdin'],
                stdin=True,
                tty=True,
            )
            await loop.run_in_executor(
                None,
                self.docker_client.api.exec_start,
                exec_instance['Id'],
                detach=False,
                tty=True,
                stream=False,
            )
        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"Error sending input: {str(e)}"
            }))

    async def stream_container_logs(self):
        try:
            for log in self.container.logs(stream=True, stdout=True, stderr=True, follow=True):
                decoded = log.decode("utf-8", errors="ignore")
                await self.send(text_data=json.dumps({
                    "type": "output",
                    "output": decoded
                }))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self.send(text_data=json.dumps({
                "type": "error",
                "message": f"Log streaming error: {str(e)}"
            }))

    async def get_ai_explanation(self, code):
        prompt = f"Explain this Python code in simple terms:\n\n{code}\n\nExplanation:"
        try:
            completion = await asyncio.to_thread(
                client.chat.completions.create,
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.5,
            )
            return completion.choices[0].message.content.strip()
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
        query = urllib.parse.urlencode(params)
        return f"{base_url}#{query}"
