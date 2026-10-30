# Model fit, tuning and context shaping

## Fit ratings (any PC)

`backend/fit.py` estimates how each library model will run on the current machine. It uses the model's own structure from the catalog (layers, KV heads, head size, sliding windows, mixture of experts) and what the PC reports:

1. **Graphics memory**, from `llama-server --list-devices` (any vendor the runtime supports). It falls back to `nvidia-smi`, then the Windows driver registry (`HardwareInformation.qwMemorySize`). Integrated graphics are treated as CPU, because they share system memory.
2. **System memory**, from psutil. About 20% (at least 4 GB) is kept free for Windows and other apps.
3. **A user correction**, from Library › This PC › Correct this (`hardware_override` in config), when detection is wrong.

For each quantization it picks a placement in this order:

| Placement | When | Launch settings |
|---|---|---|
| All on GPU | Weights plus KV cache fit with headroom | `-ngl 999`, longest context up to 64k that leaves 5% free |
| Experts on CPU | Mixture-of-experts model too big for VRAM | `--n-cpu-moe N`; attention and KV stay on the GPU |
| Layer split | Dense model too big for VRAM | `-ngl N`, the rest of the layers on the CPU |
| CPU only | No usable GPU | `-ngl 0` |

Ratings: **Recommended**, **Runs well**, **Runs slowly**, **May be unstable**, **Too large**, **Not rated** (graphics memory unknown). A benchmark result for that model replaces the estimate. "Best fit" marks the highest-quality quantization that earns the model's best rating.

These are estimates. Drivers, llama.cpp versions and other open apps all move the real numbers, so the UI says so and offers a benchmark.

## Tuning

- **Use recommended settings** saves the estimate as the model's `launch` settings in `models.json`; the runtime passes them to llama-server with `-fit off`.
- **Find best settings** runs a Smart benchmark: the estimated point plus two safer steps (fewer GPU layers, or more expert layers on the CPU), at physical cores and cores − 2.
- **Adjust** edits context, GPU layers, expert layers on the CPU and batch size by hand. **Back to automatic** clears them and returns to llama.cpp's own `-fit`.

## Context shaping

`backend/context_shaping.py` changes what a single request sends. Saved history is never changed.

- **Older tool output shrinks** to its first 900 and last 300 characters, plus a `history_read` pointer. This applies to output older than the last two user turns, and within a long run to everything but the newest 8 results, trimmed 8 at a time.
- **Re-reads**: when the same file, page, folder or search is read again, only the newest copy is sent in full.
- **Prompt-cache-friendly layout**: the plan, which changes on nearly every step, rides on the last message rather than the system message. The long prefix then stays identical between steps, and llama-server (`--cache-reuse 256`) reuses its prompt cache instead of reprocessing the whole conversation.
- **Lighter compaction input**: long tool outputs are trimmed before LLM summarization, so compaction takes fewer, faster chunks.

Request stats (`shortened`, `superseded`, `chars_saved`) are recorded in the chat's context record.
