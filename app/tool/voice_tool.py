import json
import os
from pathlib import Path
from typing import Any, Optional

from app.config import WORKSPACE_ROOT
from app.tool.base import BaseTool, ToolResult

VOICES_REGISTRY = WORKSPACE_ROOT / "voices.json"


def _load_voices() -> list:
    if not VOICES_REGISTRY.exists():
        return []
    try:
        return json.loads(VOICES_REGISTRY.read_text())
    except Exception:
        return []


def _save_voices(voices: list) -> None:
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    VOICES_REGISTRY.write_text(json.dumps(voices, indent=2))


def format_voices_list(voices: list) -> str:
    if not voices:
        return "No cloned voices found."
    lines = [f"Cloned Voices ({len(voices)} total)", "=" * 40]
    for i, v in enumerate(voices, 1):
        lines.append(f"{i}. {v.get('name', 'Unknown')}")
        lines.append(f"   ID:          {v.get('voice_id', 'N/A')}")
        if v.get("description"):
            lines.append(f"   Description: {v['description']}")
        if v.get("audio_file"):
            lines.append(f"   Source:      {v['audio_file']}")
    return "\n".join(lines)


class ListVoicesTool(BaseTool):
    name: str = "list_voices"
    description: str = "List all cloned voices stored in the local registry"
    parameters: dict = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self, **kwargs: Any) -> ToolResult:
        voices = _load_voices()
        return self.success_response(format_voices_list(voices))


class VoiceCloneTool(BaseTool):
    name: str = "voice_clone"
    description: str = (
        "Clone a voice from an audio file using the ElevenLabs API and save it to the local registry"
    )
    parameters: dict = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Display name for the cloned voice",
            },
            "audio_file": {
                "type": "string",
                "description": "Path to the audio file used for voice cloning",
            },
            "description": {
                "type": "string",
                "description": "Optional description of the voice",
            },
        },
        "required": ["name", "audio_file"],
    }

    async def execute(
        self,
        name: str,
        audio_file: str,
        description: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        api_key = os.environ.get("ELEVENLABS_API_KEY", "")
        if not api_key:
            return self.fail_response(
                "ELEVENLABS_API_KEY environment variable is not set"
            )

        audio_path = Path(audio_file)
        if not audio_path.exists():
            return self.fail_response(f"Audio file not found: {audio_file}")

        try:
            import requests

            with open(audio_path, "rb") as f:
                response = requests.post(
                    "https://api.elevenlabs.io/v1/voices/add",
                    headers={"xi-api-key": api_key},
                    data={"name": name, "description": description},
                    files={"files": (audio_path.name, f, "audio/mpeg")},
                    timeout=60,
                )

            if response.status_code != 200:
                return self.fail_response(
                    f"ElevenLabs API error {response.status_code}: {response.text}"
                )

            voice_id = response.json().get("voice_id", "")
            voices = _load_voices()
            voices.append(
                {
                    "voice_id": voice_id,
                    "name": name,
                    "description": description,
                    "audio_file": str(audio_path),
                }
            )
            _save_voices(voices)
            return self.success_response(
                f"Voice '{name}' cloned successfully.\nVoice ID: {voice_id}"
            )
        except Exception as e:
            return self.fail_response(f"Error cloning voice: {e}")
