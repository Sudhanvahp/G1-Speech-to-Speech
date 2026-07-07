"""Robot capabilities: motion and speech, plus their LLM tool schemas.

`MotionSkills` and `SpeechSkills` are Protocols (contracts). The real
implementations talk to the Unitree SDK; the mock implementations print what
they would do so the whole stack runs on any PC without a robot.
"""
