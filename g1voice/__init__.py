"""g1voice — voice-commanded motion for the Unitree G1 humanoid.

Speak to the robot; a language model maps your words to a small set of safe,
clamped motion primitives, and the robot replies through its speaker.

Runs free and offline with a local LLM (Ollama) on the G1 EDU's Jetson Orin,
or against the OpenAI cloud API.
"""

__version__ = "1.0.0"
