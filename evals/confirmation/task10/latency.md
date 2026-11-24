# Latency (seconds)

Source: 41 bot.log files (1 audio) under evals/results.

| stage | n | median | P90 |
|---|---|---|---|
| end-to-end (end of user speech -> bot starts speaking), audio runs | 2 | 5.10 | 6.31 |
|   of which: transcript ready -> bot starts speaking (LLM + TTS) | 2 | 4.19 | 5.46 |
| STT TTFB, audio runs | 4 | 0.91 | 1.35 |
| LLM TTFB, audio runs | 9 | 1.10 | 1.67 |
| TTS TTFB, audio runs | 3 | 1.48 | 2.14 |
| LLM TTFB, all runs (text + audio) | 155 | 1.05 | 7.43 |
| TTS TTFB, all runs (text + audio) | 29 | 0.95 | 1.62 |

Audio logs used:
- 20261123-185054/happy_path/attempt-1/bot.log
