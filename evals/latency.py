"""Latency numbers (median, P90) from the bot.log files of suite runs.

    uv run python evals/latency.py evals/results > evals/confirmation/task10/latency.md

Per stage, as logged by Pipecat's metrics:
  LLM TTFB   "GoogleLLMService#N TTFB: x" (or GroqLLMService)          (all logs, text and audio runs)
  TTS TTFB   "KokoroTTSService#N TTFB: x"          (all logs, text and audio runs)
  STT TTFB   "WhisperSTTService#N TTFB: x"         (audio runs only)
  End-to-end (audio runs only): from the "User stopped speaking" log line to the next
  "Bot started speaking" line, plus the STT TTFB logged just before that stop line (Pipecat measures
  STT TTFB from the end of speech, and the stop line is only logged once the transcript is ready).
Turns where the bot makes a tool call and does not speak before the next user turn are skipped.
"""

import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

from order_agent.suite import strip_ansi
TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+)")
STAGES = {
    "LLM TTFB": re.compile(r"(?:Google|Groq)LLMService#\d+ TTFB: ([\d.]+)s"),
    "TTS TTFB": re.compile(r"KokoroTTSService#\d+ TTFB: ([\d.]+)s"),
    "STT TTFB": re.compile(r"WhisperSTTService#\d+ TTFB: ([\d.]+)s"),
}


def pct(values, p):
    s = sorted(values)
    k = (len(s) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def parse(path: Path):
    stages = {k: [] for k in STAGES}
    e2e_gap, e2e_full = [], []
    audio = False
    stt_ttfb = 0.0
    stop_t = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = strip_ansi(raw)
        m = TS.match(line)
        if not m:
            continue
        t = datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S.%f").timestamp()
        for name, rx in STAGES.items():
            mm = rx.search(line)
            if mm:
                stages[name].append(float(mm.group(1)))
                if name == "STT TTFB":
                    audio = True
                    stt_ttfb = float(mm.group(1))
        if "User stopped speaking" in line:
            stop_t = t
            stop_stt = stt_ttfb
        elif "User started speaking" in line:
            stop_t = None
        elif "Bot started speaking" in line and stop_t is not None:
            e2e_gap.append(t - stop_t)
            e2e_full.append(t - stop_t + stop_stt)
            stop_t = None
    return audio, stages, e2e_gap, e2e_full


def main(root: Path) -> None:
    all_stages = {k: [] for k in STAGES}
    audio_stages = {k: [] for k in STAGES}
    gap, full = [], []
    files = sorted(root.glob("*/*/attempt-*/bot.log"))
    audio_files = []
    for f in files:
        audio, st, g, fl = parse(f)
        for k, v in st.items():
            all_stages[k] += v
            if audio:
                audio_stages[k] += v
        if audio:
            audio_files.append(f)
            gap += g
            full += fl

    def row(label, vals):
        if not vals:
            return f"| {label} | 0 | - | - |"
        return f"| {label} | {len(vals)} | {statistics.median(vals):.2f} | {pct(vals, 0.9):.2f} |"

    print("# Latency (seconds)\n")
    print(f"Source: {len(files)} bot.log files ({len(audio_files)} audio) under {root.as_posix()}.\n")
    print("| stage | n | median | P90 |\n|---|---|---|---|")
    print(row("end-to-end (end of user speech -> bot starts speaking), audio runs", full))
    print(row("  of which: transcript ready -> bot starts speaking (LLM + TTS)", gap))
    print(row("STT TTFB, audio runs", audio_stages["STT TTFB"]))
    print(row("LLM TTFB, audio runs", audio_stages["LLM TTFB"]))
    print(row("TTS TTFB, audio runs", audio_stages["TTS TTFB"]))
    print(row("LLM TTFB, all runs (text + audio)", all_stages["LLM TTFB"]))
    print(row("TTS TTFB, all runs (text + audio)", all_stages["TTS TTFB"]))
    print("\nAudio logs used:")
    for f in audio_files:
        print(f"- {f.relative_to(root).as_posix()}")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "evals/results"))
