#!/usr/bin/env python3
"""
Simplified OpenManus Web Backend
This version has minimal dependencies and wraps the core agent functionality
"""

import asyncio
import json
import logging
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_task_results = {}
_task_lock = threading.Lock()


def _send_json(handler, status_code, payload):
    """Send a JSON response with correct HTTP header ordering."""
    body = json.dumps(payload).encode()
    handler.send_response(status_code)
    handler.send_header('Content-Type', 'application/json')
    handler.send_header('Content-Length', str(len(body)))
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type')
    handler.end_headers()
    handler.wfile.write(body)


def _run_task(task_id, prompt):
    """Execute a task in its own event loop with a fresh agent instance.

    Each task creates its own Manus agent because asyncio objects are bound
    to the event loop they were created in; sharing across threads/loops
    causes RuntimeError.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    agent = None
    try:
        from app.agent.manus import Manus
        agent = loop.run_until_complete(Manus.create())
        loop.run_until_complete(agent.run(prompt))
        with _task_lock:
            _task_results[task_id] = {
                "status": "completed",
                "result": "Task executed successfully",
            }
        logger.info(f"Task {task_id} completed")
    except Exception as e:
        with _task_lock:
            _task_results[task_id] = {"status": "error", "error": str(e)}
        logger.error(f"Task {task_id} failed: {e}")
    finally:
        if agent is not None:
            try:
                loop.run_until_complete(agent.cleanup())
            except Exception as e:
                logger.warning(f"Agent cleanup failed for task {task_id}: {e}")
        loop.close()


class AgentRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for OpenManus Web API"""

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/health':
            _send_json(self, 200, {"status": "healthy"})
            return

        if path == '/api/status':
            _send_json(self, 200, {"status": "ready"})
            return

        if path.startswith('/api/task/'):
            task_id = path[len('/api/task/'):]
            with _task_lock:
                result = _task_results.get(task_id)
            if result is None:
                _send_json(self, 404, {"error": "Task not found"})
            else:
                _send_json(self, 200, result)
            return

        _send_json(self, 404, {"error": "Not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))

        if path != '/api/execute':
            _send_json(self, 404, {"error": "Not found"})
            return

        try:
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            _send_json(self, 400, {"error": "Invalid JSON"})
            return

        prompt = (data.get('prompt') or '').strip()
        if not prompt:
            _send_json(self, 400, {"error": "Prompt cannot be empty"})
            return

        task_id = uuid.uuid4().hex
        with _task_lock:
            _task_results[task_id] = {"status": "processing"}

        logger.info(f"Executing task {task_id}: {prompt[:100]}")
        threading.Thread(
            target=_run_task, args=(task_id, prompt), daemon=True
        ).start()

        _send_json(self, 202, {
            "status": "processing",
            "task_id": task_id,
            "message": "Task queued for execution",
        })

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)


def run_server(host='0.0.0.0', port=8000):
    httpd = HTTPServer((host, port), AgentRequestHandler)
    logger.info(f"OpenManus Web Backend running at http://{host}:{port}")
    logger.info("Endpoints:")
    logger.info("  GET  /health")
    logger.info("  POST /api/execute")
    logger.info("  GET  /api/task/<task_id>")
    logger.info("  GET  /api/status")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        httpd.shutdown()


if __name__ == '__main__':
    import sys
    host = sys.argv[1] if len(sys.argv) > 1 else '0.0.0.0'
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    run_server(host, port)
