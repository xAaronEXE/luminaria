"""Local model generation options. Each GGUF retains its own chat template."""

import re


def model_family(model):
    names = ' '.join(str(model.get(key, '')) for key in ('id', 'name', 'family'))
    if re.search(r'\bqwen[ -]?3(?![.\d]|[- ](?:coder|next))', names, re.I):
        return 'qwen3'
    if re.search(r'\bqwen', names, re.I):
        return 'qwen'
    for name in ('llama', 'gemma', 'deepseek'):
        if re.search(r'\b' + name, names, re.I):
            return name
    return None


def generation_options(model, reasoning):
    # Qwen3 hybrid chat templates expose a thinking switch. Other supported
    # families keep their embedded chat template and native reasoning behavior.
    family = model_family(model)
    if family == 'qwen3':
        return {
            'chat_template_kwargs': {'enable_thinking': bool(reasoning)},
            'top_p': 0.95 if reasoning else 0.8,
            'top_k': 20,
        }
    if family is None:
        # Keep the existing compatibility behavior for custom model IDs.
        return {'chat_template_kwargs': {'enable_thinking': bool(reasoning)}}
    return {}
