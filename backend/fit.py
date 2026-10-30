"""Per-PC fit estimates for models in the library.

Works on any machine: it starts from what this PC reports (graphics memory,
system memory, whether the GPU is integrated) and each model's own structure
(layers, attention heads, sliding windows, mixture of experts), then works
out where the model can live and how much context fits.

These are estimates, not measurements. Drivers, other apps and llama.cpp
versions all move the numbers, so every rating says so and the benchmark in
Settings > Hardware & tuning replaces the guess with a measurement.
"""
import math
import re

GB = 1024 ** 3
MB = 1024 ** 2
FIT_MARGIN = 512 * MB              # matches the runtime's -fitt 512
DESKTOP_VRAM = int(0.8 * GB)       # what Windows and other apps typically hold when free memory is unknown
CONTEXT_STEPS = (131072, 65536, 40960, 32768, 16384, 8192)
COMFORT_CONTEXT = 65536            # largest context recommended by default; users can go higher
# Share of a mixture-of-experts file that is expert weights (movable to the CPU).
EXPERT_SHARE = {'qwen3moe': 0.9, 'gpt-oss': 0.88, 'llama4': 0.85, 'mixtral': 0.9, 'deepseek2': 0.9}
# How much faster graphics memory reads than system memory. Used only for
# relative speed tiers, never shown as tokens per second.
VRAM_TO_RAM_SPEED = 8.0

RATINGS = {
    'recommended': ('Recommended', 'Runs fully in graphics memory with room for long context.'),
    'good': ('Runs well', 'Fits with good speed. Context or headroom is somewhat limited.'),
    'slow': ('Runs slowly', 'Fits, but part of the model runs from system memory, so replies come slowly.'),
    'unstable': ('May be unstable', 'Only just fits. Expect out-of-memory errors or freezes under load, or with other apps open.'),
    'too_large': ('Too large', 'Needs more memory than this PC has.'),
    'unknown': ('Not rated', 'Graphics memory could not be read. Set it in Settings > Hardware & tuning, or run a benchmark.'),
}
ORDER = ['recommended', 'good', 'slow', 'unstable', 'too_large', 'unknown']
INTEGRATED = re.compile(r'\b(uhd|iris|intel\(r\) graphics|radeon\(tm\) graphics|radeon graphics|vega \d+ graphics|apple m\d|adreno)\b', re.I)


def compute_buffer(ubatch=512):
    """Scratch memory llama.cpp keeps on the GPU for prompt processing."""
    return 256 * MB + ubatch * MB // 2


def parse_billions(text):
    match = re.search(r'([\d.]+)\s*B', text or '')
    return float(match.group(1)) if match else None


def machine(info, override=None):
    """Reduce hardware.information() plus a user override to the numbers the estimator needs."""
    info = info or {}
    devices = info.get('devices') or []
    gpus = [g for g in info.get('gpus') or [] if g.get('vram_bytes')]
    if not gpus:   # AMD and Intel: the driver registry knows the real size even when no tool reports it
        gpus = [dict(g, used_bytes=None) for g in info.get('registry_vram') or [] if not INTEGRATED.search(g.get('name') or '')]
    best = max(devices, key=lambda d: d.get('total_bytes') or 0, default=None)
    name = (best or {}).get('name') or (gpus[0]['name'] if gpus else ((info.get('gpus') or [{}])[0].get('name') or ''))
    total = (best or {}).get('total_bytes') or (max(g['vram_bytes'] for g in gpus) if gpus else None)
    free = (best or {}).get('free_bytes')
    if free is None and gpus:
        top = max(gpus, key=lambda g: g['vram_bytes'])
        if top.get('used_bytes') is not None: free = top['vram_bytes'] - top['used_bytes']
    integrated = bool(name and INTEGRATED.search(name))
    checked = info.get('devices') is not None      # llama.cpp answered, even if it found no GPU
    source = 'llama.cpp' if (best or (checked and not gpus)) else ('driver' if gpus else None)
    override = override or {}
    if override.get('vram_bytes') is not None:
        total, free, source = int(override['vram_bytes']), None, 'you'
        integrated = bool(override.get('integrated', False))
    if integrated: total, free = 0, None          # shared memory: plan as CPU, not as separate VRAM
    ram = info.get('ram_bytes') or 0
    return {'gpu': name or None, 'vram_total': total, 'vram_free': free, 'integrated': integrated,
            'ram_total': ram, 'cores': info.get('physical_cores'), 'source': source}


def _vram_budget(hw, ubatch):
    if not hw['vram_total']: return 0
    usable = hw['vram_free'] if hw['vram_free'] is not None else hw['vram_total'] - DESKTOP_VRAM
    return max(0, usable - FIT_MARGIN - compute_buffer(ubatch))


def _ram_budget(hw):
    ram = hw['ram_total'] or 0
    return max(0, ram - max(4 * GB, int(ram * 0.2)))   # keep Windows and other apps comfortable


def _speed(gpu_read, cpu_read):
    """Speed relative to the same model fully on the GPU: 1.0 = all GPU."""
    total = gpu_read + cpu_read
    return 1.0 if not cpu_read else total / (gpu_read + cpu_read * VRAM_TO_RAM_SPEED)


def estimate(model, hw, cache_bytes, ubatch=512):
    """Plan one quantization on this machine.

    model: bytes, layers, architecture, context_supported, active_ratio (MoE only).
    cache_bytes(context) -> KV cache bytes at that context (q8_0, sliding windows included).
    """
    weights = model['bytes']; layers = max(1, model.get('layers') or 1)
    supported = model.get('context_supported') or 32768
    contexts = sorted({min(supported, c) for c in CONTEXT_STEPS}, reverse=True)
    gpu = _vram_budget(hw, ubatch); ram = _ram_budget(hw)
    moe_share = EXPERT_SHARE.get(model.get('architecture')) if model.get('active_ratio') else None
    plan = squeezed = None

    # 1. Fully on the GPU, at the longest comfortable context that fits.
    if gpu:
        # Longest context that leaves headroom; only if none does, the longest that fits at all.
        for headroom in (0.05, 0.0):
            for ctx in contexts:
                if ctx > COMFORT_CONTEXT and any(c <= COMFORT_CONTEXT for c in contexts): continue
                need = weights + cache_bytes(ctx)
                if need <= gpu * (1 - headroom):
                    plan = {'placement': 'gpu', 'context': ctx, 'gpu_layers': -1, 'cpu_moe': 0,
                            'vram_used': need, 'ram_used': 0, 'speed': 1.0, 'spare': (gpu - need) / max(gpu, 1)}
                    break
            if plan: break
        # A plan that only squeezes in with a short context and no headroom is a last resort:
        # a comfortable split usually serves people better.
        if plan and plan['context'] < min(16384, supported) and plan['spare'] < 0.05:
            squeezed, plan = plan, None
        else:
            squeezed = None

    # 2. Mixture of experts: keep attention and cache on the GPU, move whole expert blocks to the CPU.
    if not plan and gpu and moe_share:
        expert_layer = weights * moe_share / layers
        shared = weights - weights * moe_share
        for ctx in [c for c in contexts if c <= 32768] or contexts[-1:]:
            kv = cache_bytes(ctx)
            if shared + kv > gpu: continue
            moved = max(0, math.ceil((weights + kv - gpu) / expert_layer))
            if moved > layers: continue
            cpu_bytes = moved * expert_layer
            if cpu_bytes > ram: continue
            ratio = model['active_ratio']
            gpu_read = shared + (layers - moved) * expert_layer * ratio
            cpu_read = cpu_bytes * ratio
            plan = {'placement': 'moe', 'context': ctx, 'gpu_layers': -1, 'cpu_moe': moved,
                    'vram_used': weights + kv - cpu_bytes, 'ram_used': cpu_bytes, 'speed': _speed(gpu_read, cpu_read),
                    'spare': (gpu - (weights + kv - cpu_bytes)) / max(gpu, 1)}
            break

    # 3. Dense split: as many whole layers on the GPU as fit, the rest on the CPU.
    if not plan and gpu:
        for ctx in [c for c in contexts if c <= 32768] or contexts[-1:]:
            kv = cache_bytes(ctx)
            fixed = weights * 0.06                   # embeddings and output head
            per_layer = (weights - fixed + kv) / layers
            on_gpu = int((gpu - fixed) // per_layer) if gpu > fixed else 0
            on_gpu = max(0, min(layers, on_gpu))
            cpu_bytes = (layers - on_gpu) * per_layer
            if on_gpu == 0 or cpu_bytes > ram: continue
            plan = {'placement': 'split', 'context': ctx, 'gpu_layers': on_gpu, 'cpu_moe': 0,
                    'vram_used': fixed + on_gpu * per_layer, 'ram_used': cpu_bytes,
                    'speed': _speed(fixed + on_gpu * per_layer, cpu_bytes), 'spare': 0.0}
            break

    # 4. CPU only.
    if not plan:
        for ctx in [c for c in contexts if c <= 32768] or contexts[-1:]:
            need = weights + cache_bytes(ctx)
            if need <= ram:
                ratio = model.get('active_ratio') or 1.0
                plan = {'placement': 'cpu', 'context': ctx, 'gpu_layers': 0, 'cpu_moe': 0, 'vram_used': 0, 'ram_used': need,
                        'speed': (1 / VRAM_TO_RAM_SPEED) * (1 / max(ratio, 0.05)) ** 0.5 if ratio < 1 else 1 / VRAM_TO_RAM_SPEED,
                        'spare': (ram - need) / max(ram, 1)}
                break

    if not plan and squeezed: plan = squeezed
    if not plan:
        return {'rating': 'too_large', 'placement': None, 'context': None, 'gpu_layers': None, 'cpu_moe': None,
                'vram_used': None, 'ram_used': None, 'speed': None, 'detail': f'Needs about {_gb(weights + cache_bytes(8192))} at 8k context.'}

    plan['rating'] = _rate(plan, hw, model)
    plan['detail'] = _describe(plan, layers)
    plan['ubatch'] = ubatch if plan['placement'] in ('gpu', 'moe') else 128
    return plan


def _rate(plan, hw, model):
    if not hw['vram_total'] and not hw['integrated'] and hw['source'] is None: unknown = True
    else: unknown = False
    tight_context = plan['context'] < min(16384, model.get('context_supported') or 16384)
    if plan['placement'] == 'gpu':
        if plan['context'] < 8192 or plan['spare'] < 0.03: return 'unstable'
        if not tight_context and plan['spare'] >= 0.10: return 'recommended'
        return 'good'
    if plan['placement'] == 'moe':
        if plan['context'] < 8192: return 'unstable'
        return 'good' if plan['speed'] >= 0.3 else 'slow'
    if plan['placement'] == 'split':
        if plan['speed'] < 0.18: return 'unstable' if plan['ram_used'] > _ram_budget(hw) * 0.85 else 'slow'
        return 'slow' if plan['speed'] < 0.45 else 'good'
    # CPU only: small models are usable; big dense ones crawl and strain memory.
    if unknown: return 'unknown'
    active = model['bytes'] * (model.get('active_ratio') or 1.0)
    if plan['spare'] < 0.08: return 'unstable'
    return 'good' if active <= 3 * GB else 'slow'


def _gb(n): return f'{n / GB:.1f} GB'


def _tokens(n): return f'{n // 1024}k'


def _describe(plan, layers):
    ctx = _tokens(plan['context'])
    if plan['placement'] == 'gpu':
        return f"Fits fully in graphics memory with {ctx} context ({_gb(plan['vram_used'])} used)."
    if plan['placement'] == 'moe':
        return (f"Keeps attention and context on the GPU and runs experts for {plan['cpu_moe']} of {layers} layers "
                f"from system memory ({_gb(plan['ram_used'])}) at {ctx} context.")
    if plan['placement'] == 'split':
        return f"{plan['gpu_layers']} of {layers} layers on the GPU, the rest from system memory ({_gb(plan['ram_used'])}) at {ctx} context."
    return f"Runs on the CPU from system memory ({_gb(plan['ram_used'])}) at {ctx} context."


def public(plan, measured=None):
    """What the library shows. A measured benchmark outranks the estimate."""
    rating = plan['rating']
    if measured and measured.get('tps'):
        tps = measured['tps']
        rating = 'recommended' if tps >= 25 and rating in ('recommended', 'good') else 'good' if tps >= 12 else 'slow'
    label, meaning = RATINGS[rating]
    return {'rating': rating, 'label': label, 'meaning': meaning, 'detail': plan.get('detail', ''),
            'placement': plan.get('placement'), 'context': plan.get('context'),
            'settings': {'context': plan.get('context'), 'gpu_layers': plan.get('gpu_layers'), 'cpu_moe': plan.get('cpu_moe'), 'ubatch': plan.get('ubatch', 512)},
            'vram_used': plan.get('vram_used'), 'ram_used': plan.get('ram_used'),
            'speed': round(plan['speed'], 2) if plan.get('speed') is not None else None,
            'measured': bool(measured and measured.get('tps')),
            'note': 'Measured on this PC.' if measured and measured.get('tps') else 'Estimate for this PC. Results vary; benchmark to confirm.'}
