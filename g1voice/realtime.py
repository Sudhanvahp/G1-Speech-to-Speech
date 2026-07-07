"""Optional low-latency mode: OpenAI Realtime API <-> G1 microphone/speaker.

Streams the robot's raw microphone multicast up to the Realtime API and plays
returned audio through the speaker, executing motion tool calls inline. This is
cloud-only (OpenAI) and needs internet on the Jetson.

Requires `websockets`. The default `asr` mode is simpler and free; use this
only when you want the snappier, interruptible conversation feel.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import socket
import struct

from .agent import VoiceAgent
from .config import Settings
from .skills.base import TOOL_SCHEMAS

log = logging.getLogger(__name__)

_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-realtime"
_CHUNK = 4096


def _mic_chunks(group: str, port: int, iface_ip: str):
    """Yield raw PCM chunks from the G1 microphone multicast feed."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", port))
    mreq = struct.pack("4s4s", socket.inet_aton(group), socket.inet_aton(iface_ip))
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    try:
        while True:
            data, _ = sock.recvfrom(_CHUNK)
            yield data
    finally:
        sock.close()


def run_realtime(agent: VoiceAgent, settings: Settings) -> None:
    import websockets  # imported here so the dependency is optional

    robot = settings.robot
    headers = {"Authorization": f"Bearer {settings.llm.api_key}"}

    async def session() -> None:
        async with websockets.connect(_REALTIME_URL, additional_headers=headers) as ws:
            await ws.send(json.dumps({"type": "session.update", "session": {
                "instructions": settings.system_prompt,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "tools": TOOL_SCHEMAS,
                "turn_detection": {"type": "server_vad"},
            }}))
            await asyncio.gather(_uplink(ws, robot), _downlink(ws, agent))

    async def _uplink(ws, robot) -> None:
        loop = asyncio.get_running_loop()
        chunks = _mic_chunks(robot.mic_multicast_group,
                             robot.mic_multicast_port, robot.self_ip)
        while True:
            chunk = await loop.run_in_executor(None, next, chunks)
            await ws.send(json.dumps({
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(chunk).decode(),
            }))

    async def _downlink(ws, agent: VoiceAgent) -> None:
        async for raw in ws:
            event = json.loads(raw)
            kind = event.get("type")
            if kind == "response.audio.delta":
                agent._speech.play_pcm(base64.b64decode(event["delta"]))  # noqa: SLF001
            elif kind == "input_audio_buffer.speech_started":
                agent._speech.play_stop()  # barge-in  # noqa: SLF001
            elif kind == "response.function_call_arguments.done":
                result = agent._execute_tool(  # noqa: SLF001
                    event["name"], json.loads(event.get("arguments") or "{}"))
                await ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {"type": "function_call_output",
                             "call_id": event["call_id"], "output": result},
                }))
                await ws.send(json.dumps({"type": "response.create"}))

    log.info("Realtime mode connecting ...")
    try:
        asyncio.run(session())
    except KeyboardInterrupt:
        log.info("Shutting down")
