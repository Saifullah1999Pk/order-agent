# Latency (seconds)

Source: 9 bot.log files (9 audio) under evals/results (one run only, see file name).

| stage | n | median | P90 |
|---|---|---|---|
| end-to-end (end of user speech -> bot starts speaking), audio runs | 28 | 2.73 | 3.64 |
|   of which: transcript ready -> bot starts speaking (LLM + TTS) | 28 | 1.87 | 2.65 |
| STT TTFB, audio runs | 31 | 0.86 | 1.13 |
| LLM TTFB, audio runs | 51 | 0.55 | 0.84 |
| TTS TTFB, audio runs | 43 | 0.95 | 1.84 |
| LLM TTFB, all runs (text + audio) | 51 | 0.55 | 0.84 |
| TTS TTFB, all runs (text + audio) | 43 | 0.95 | 1.84 |

Audio logs used:
- 20261123-205926/happy_path/attempt-1/bot.log
- 20261123-205926/happy_path/attempt-2/bot.log
- 20261123-205926/happy_path/attempt-3/bot.log
- 20261123-205926/pushes_forbidden/attempt-1/bot.log
- 20261123-205926/pushes_forbidden/attempt-2/bot.log
- 20261123-205926/pushes_forbidden/attempt-3/bot.log
- 20261123-205926/sold_out_substitute/attempt-1/bot.log
- 20261123-205926/sold_out_substitute/attempt-2/bot.log
- 20261123-205926/sold_out_substitute/attempt-3/bot.log
