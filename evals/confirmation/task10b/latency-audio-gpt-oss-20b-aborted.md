# Latency (seconds)

Source: 3 bot.log files (2 audio) under evals/results (one run only, see file name).

| stage | n | median | P90 |
|---|---|---|---|
| end-to-end (end of user speech -> bot starts speaking), audio runs | 2 | 3.66 | 4.17 |
|   of which: transcript ready -> bot starts speaking (LLM + TTS) | 2 | 2.88 | 3.44 |
| STT TTFB, audio runs | 3 | 0.79 | 0.82 |
| LLM TTFB, audio runs | 8 | 0.63 | 0.88 |
| TTS TTFB, audio runs | 4 | 0.90 | 1.04 |
| LLM TTFB, all runs (text + audio) | 11 | 0.59 | 0.88 |
| TTS TTFB, all runs (text + audio) | 4 | 0.90 | 1.04 |

Audio logs used:
- 20261123-211953/happy_path/attempt-2/bot.log
- 20261123-211953/happy_path/attempt-3/bot.log
