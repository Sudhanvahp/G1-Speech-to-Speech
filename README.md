# G1 Voice — talk to your Unitree G1, it moves

Speak to the robot; a language model turns your words into **safe, clamped
motion** (stand, walk, turn, wave, handshake, stop) and the robot replies
through its speaker.

Runs **free and offline** on the G1 EDU's Jetson Orin using a local LLM
(Ollama), or against the OpenAI cloud if you prefer.

> The viral *"G1 hears you talk and moves in real time"* clip is a Unitree R&D
> demo — **not a shipped feature**. This project builds a practical version on
> officially supported SDK pieces: the VUI/Audio service (ASR, TTS, speaker,
> LED) and `LocoClient` motion.

---

## 1. What's in the box

```
g1voice/
  config.py        Typed, validated settings (all tunables live here)
  brain.py         LLM tool-calling loop (provider-agnostic)
  agent.py         Orchestration: safety -> brain -> skills -> speech
  asr.py           Speech input from the robot's built-in ASR
  realtime.py      Optional low-latency OpenAI Realtime mode (cloud-only)
  cli.py           Command-line entrypoint
  skills/
    base.py        Contracts (Protocols) + LLM tool schemas
    safety.py      Pure clamp/stop-word logic (unit-tested)
    motion.py      Real motion via Unitree LocoClient
    speech.py      Real speech/LED via Unitree AudioClient
    mock.py        Fake robot for PC testing (same clamps)
check_hardware.py  Phase-0 smoke test (run on the robot)
tests/             Unit tests for the safety layer (no robot needed)
```

**Design:** the LLM only ever *chooses* a tool; the agent executes it through
the clamped skill layer. Velocity/duration limits are identical in dry-run and
on the robot because both import `skills/safety.py`. Emergency stop words are
matched locally and never reach the LLM, so "stop" works even offline.

---

## 2. How the "brain" works (important)

Small local models are unreliable at deciding robot motion — in testing they
narrated actions without performing them, or called the wrong tool. Since motion
is safety-critical, the **default `hybrid` brain does NOT let the model actuate
the robot**:

- **Motion commands** ("walk forward", "turn left", "wave", "stop") are matched
  by deterministic rules → executed **instantly and correctly**, and they keep
  working even if the LLM is offline.
- **Conversation** ("what can you do", "who made you") is handled by the LLM.

Three selectable brains (`--brain`):

| Brain | Motion | Conversation | Needs |
|---|---|---|---|
| `hybrid` *(default)* | deterministic rules | LLM | Ollama (chat only) |
| `keyword` | deterministic rules | fixed help text | **nothing** |
| `llm` | model decides | LLM | Ollama or OpenAI |

## 3. Try it on your PC first (no robot, free)

```bash
pip install -r requirements.txt

# Zero setup — no LLM at all, works instantly:
python main.py --dry-run --brain keyword
```

Type `wave`, `walk forward`, `turn right`, `shake hands`, `stop`. Each is logged
as the action the real robot would take.

**For conversation too, add the free local LLM (Ollama):**

```bash
# install Ollama once from https://ollama.com, then:
ollama pull qwen2.5:3b
ollama serve                 # leave running
python main.py --dry-run     # default = hybrid brain
```

Cloud instead of local: `set OPENAI_API_KEY=sk-...` then
`python main.py --dry-run --provider openai`.

Run the safety unit tests any time:

```bash
python -m unittest discover -s tests
```

---

## 4. Connect to the robot

**Network (both options need this):**
1. Power on the G1 (it boots damped/seated).
2. Connect your laptop to the robot by **Ethernet** and set your wired IPv4 to
   `192.168.123.222 / 255.255.255.0`, **or** join the robot's WiFi hotspot
   (credentials in the Unitree manual).
3. SSH into the onboard Jetson (PC2): `ssh unitree@192.168.123.164`
   (base board is `.161`; password is in your manual).

**Install on the Jetson (once):**
```bash
sudo apt install -y python3-pip git
git clone https://github.com/unitreerobotics/unitree_sdk2_python
cd unitree_sdk2_python && pip3 install -e . && cd ..

# copy this project over from your PC, e.g.:
#   scp -r PROJECT_8_G1_SPEECH_TO_SPEECH unitree@192.168.123.164:~/g1_voice
cd ~/g1_voice
pip3 install -r requirements.txt

# free local brain on the robot:
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2 && ollama serve &   # runs on the Jetson, no internet needed
```

**Find your interface name** (the one with a `192.168.123.x` address):
```bash
ip addr        # usually eth0
```

---

## 5. Run on the robot

```bash
# Phase 0 — hardware check, ROBOT ON A HARNESS:
python3 check_hardware.py --iface eth0

# Voice agent (free, offline, local LLM):
python3 main.py --iface eth0
```

Say: "stand up", "wave", "walk forward", "turn left", "shake my hand".
**Say "stop" or "freeze" to halt immediately** (bypasses the AI).

Cloud brain instead: `python3 main.py --iface eth0 --provider openai`
(needs `OPENAI_API_KEY` and internet on the Jetson).

Lower-latency streaming voice (cloud-only, optional):
`python3 main.py --iface eth0 --provider openai --mode realtime`

### Auto-start on boot (production, on the Jetson)

Create `/etc/systemd/system/g1voice.service`:

```ini
[Unit]
Description=G1 Voice Agent
After=network-online.target ollama.service
Wants=network-online.target

[Service]
User=unitree
WorkingDirectory=/home/unitree/g1_voice
Environment=G1_IFACE=eth0
Environment=G1_PROVIDER=local
ExecStart=/usr/bin/python3 -m g1voice
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now ollama g1voice
journalctl -u g1voice -f        # watch logs
```

The agent restarts automatically on failure and comes up after Ollama on boot.

---

## 6. Configuration

All settings have safe defaults; override via env vars (or a `.env`, see
`.env.example`) or CLI flags. CLI wins over env.

| Variable | Default | Meaning |
|---|---|---|
| `G1_PROVIDER` | `local` | `local` (Ollama, free) or `openai` (cloud) |
| `G1_LOCAL_MODEL` | `llama3.2` | Ollama model (`qwen2.5:3b` is better at tools) |
| `G1_OLLAMA_URL` | `http://localhost:11434/v1` | Ollama endpoint |
| `OPENAI_API_KEY` | — | required if `G1_PROVIDER=openai` |
| `G1_IFACE` | `eth0` | robot network interface |
| `G1_WAKE_WORD` | — | if set, ignore speech without this phrase |

Safety limits (edit `g1voice/config.py` `SafetyConfig`): `max_vx=0.4 m/s`,
`max_vyaw=0.5 rad/s`, `max_walk_seconds=3.0`, stop words
`stop/freeze/halt/emergency`.

---

## 7. Safety checklist (read before any motion)

- First runs on the **gantry/harness**; open space, no people within 2 m.
- Keep the **physical remote in hand** — its e-stop overrides all software.
- Confirm you can drive the robot with the joystick first (it must be in normal
  locomotion mode, or `LocoClient` commands are rejected).
- The clamps and local stop word are your software safety net, not a substitute
  for the hardware e-stop.

---

## 8. Adding a new command

1. Add a method to `RealMotionSkills` (and `MockMotionSkills`) in
   `g1voice/skills/`.
2. Add a matching entry to `TOOL_SCHEMAS` in `g1voice/skills/base.py`.

`validate_tools()` checks at startup that every tool has a method, so a mismatch
fails fast instead of at runtime.
