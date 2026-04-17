# OpenManus Web Interface Setup

Welcome to OpenManus Web! This is a full-stack web application for interacting with the OpenManus autonomous AI agent.

## 📋 Components

- **Backend**: Python HTTP server that manages the OpenManus agent
- **Frontend**: Responsive HTML/CSS/JS interface for submitting tasks
- **Configuration**: Uses your existing OpenManus config with LLM APIs

## 🚀 Quick Start

### Option 1: Simple Python Server (Recommended - No Dependencies!)

```bash
# Terminal 1: Start Backend (uses built-in Python server)
python simple_backend.py

# Terminal 2: Start Frontend (in the same directory)
python3 -m http.server 5000
```

Then open your browser to:
- **Frontend**: http://localhost:5000/web-frontend.html
- **API Health**: http://localhost:8000/health

### Option 2: Automated Startup Script

```bash
chmod +x start_web.sh
./start_web.sh
```

This will:
- Start the simple backend on port 8000
- Start the HTTP server on port 5000
- Automatically open your browser

Servers will keep running until you press Ctrl+C

## 📝 Configuration

The web interface automatically uses your OpenManus configuration from `config/config.toml`. Make sure it includes:

```toml
[llm]
model = "your-model"
base_url = "your-api-endpoint"
api_key = "your-api-key"
```

## 🎯 Features

- **Simple Interface**: Enter your task and see results
- **Task Execution**: Runs complex multi-step tasks
- **Status Monitoring**: Real-time status updates
- **Error Handling**: Clear error messages and logging
- **Responsive Design**: Works on desktop and mobile

## 🔧 API Endpoints

### Health Check
```bash
GET /health
```

### Execute Task (async)
```bash
POST /api/execute
Content-Type: application/json

{ "prompt": "Your task here" }
```

Returns `202 Accepted` immediately with a `task_id`:
```json
{
  "status": "processing",
  "task_id": "29ebfef3ec354a66be3926cb1d1b409a",
  "message": "Task queued for execution"
}
```

### Poll Task Result
```bash
GET /api/task/<task_id>
```

Returns one of:
```json
{ "status": "processing" }
{ "status": "completed", "result": "..." }
{ "status": "error", "error": "..." }
```

### Server Status
```bash
GET /api/status
```

## 🐛 Troubleshooting

### Backend won't start
- Ensure all Python dependencies are installed: `pip install -r requirements.txt`
- Check that port 8000 is not in use
- Verify your LLM configuration in `config/config.toml`

### Frontend can't connect to backend
- Make sure backend is running on port 8000
- Check browser console for CORS errors
- Verify firewall settings

### Tasks failing
- Check the browser console and backend logs
- Ensure your LLM API keys are valid
- Verify network connectivity

## 📚 More Information

- [OpenManus GitHub](https://github.com/FoundationAgents/OpenManus)
- [MetaGPT Documentation](https://docs.deepwalk.io/en/)

## 🤝 Contributing

To extend the web interface:

1. Modify `simple_backend.py` to add new API endpoints
2. Update `web-frontend.html` to add new UI features
3. Test thoroughly before committing

## 📄 License

Same as OpenManus - MIT License
