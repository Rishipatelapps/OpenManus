#!/usr/bin/env python3
"""
Simplified OpenManus Web Backend
This version has minimal dependencies and wraps the core agent functionality
"""

import asyncio
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global state
_agent_instance = None
_agent_lock = threading.Lock()
_task_results = {}

async def get_or_create_agent():
    """Lazy load the agent"""
    global _agent_instance
    if _agent_instance is None:
        try:
            from app.agent.manus import Manus
            _agent_instance = await Manus.create()
            logger.info("✅ Agent initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize agent: {e}")
            raise
    return _agent_instance

class AgentRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler for OpenManus Web API"""

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # CORS headers
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

        if path == '/health':
            response = {"status": "healthy", "agent": "ready"}
            self.wfile.write(json.dumps(response).encode())

        elif path == '/api/status':
            response = {"status": "ready", "agent": _agent_instance is not None}
            self.wfile.write(json.dumps(response).encode())

        else:
            response = {"error": "Not found"}
            self.send_response(404)
            self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        content_length = int(self.headers.get('Content-Length', 0))

        # CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

        if path == '/api/execute':
            try:
                body = self.rfile.read(content_length).decode('utf-8')
                data = json.loads(body)
                prompt = data.get('prompt', '').strip()

                if not prompt:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    response = {"error": "Prompt cannot be empty"}
                    self.wfile.write(json.dumps(response).encode())
                    return

                # Execute task asynchronously
                task_id = str(len(_task_results))
                logger.info(f"📝 Executing task {task_id}: {prompt[:100]}...")

                # Run in background
                def execute_task():
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        agent = loop.run_until_complete(get_or_create_agent())
                        loop.run_until_complete(agent.run(prompt))
                        _task_results[task_id] = {
                            "status": "completed",
                            "result": "Task executed successfully"
                        }
                        logger.info(f"✅ Task {task_id} completed")
                    except Exception as e:
                        _task_results[task_id] = {
                            "status": "error",
                            "error": str(e)
                        }
                        logger.error(f"❌ Task {task_id} failed: {e}")
                    finally:
                        loop.close()

                thread = threading.Thread(target=execute_task, daemon=True)
                thread.start()

                # Immediate response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    "status": "processing",
                    "task_id": task_id,
                    "message": "Task queued for execution"
                }
                self.wfile.write(json.dumps(response).encode())

            except json.JSONDecodeError:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"error": "Invalid JSON"}
                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {"error": str(e)}
                self.wfile.write(json.dumps(response).encode())
                logger.error(f"Error: {e}")

        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"error": "Not found"}
            self.wfile.write(json.dumps(response).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging"""
        if args[1] != 200:
            logger.info(f"{args[0]} - {args[1]}")

def run_server(host='0.0.0.0', port=8000):
    """Start the HTTP server"""
    server_address = (host, port)
    httpd = HTTPServer(server_address, AgentRequestHandler)

    logger.info(f"")
    logger.info(f"🌐 OpenManus Web Backend")
    logger.info(f"📡 Server running at http://{host}:{port}")
    logger.info(f"")
    logger.info(f"Endpoints:")
    logger.info(f"  GET  /health          - Health check")
    logger.info(f"  POST /api/execute     - Execute task")
    logger.info(f"  GET  /api/status      - Get server status")
    logger.info(f"")
    logger.info(f"Frontend available at: http://localhost:5000/web-frontend.html")
    logger.info(f"")
    logger.info(f"Press Ctrl+C to stop")
    logger.info(f"")

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
