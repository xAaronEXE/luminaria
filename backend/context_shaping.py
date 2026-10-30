"""Shape one live request so long agent runs stay fast and fit more work.

Saved history is never edited; only what a single request sends changes.

1. Older tool outputs shrink to a head-and-tail excerpt with a pointer to the
   full text (history_read). Tool output is most of an agent's context, and
   the model rarely needs the full text of a file it read several turns ago.
2. When the same file or page was read again later, only the newest copy is
   sent in full; earlier copies become a one-line pointer.
3. Fast-changing working state (the plan) rides on the last message instead of
   the system message, so the long prefix stays byte-identical between steps
   and llama.cpp can reuse its prompt cache instead of reprocessing it.

Decisions depend only on message order and user-turn boundaries, so the same
history always produces the same request (which also keeps the cache warm).
"""
import json
import re

ACTION = re.compile(r'^Action ([A-Za-z0-9]{8,64}): ')
KEEP_TURNS = 2          # tool output from the last N user turns stays whole
KEEP_RESULTS = 8        # ...but within a long run only the newest results stay whole
BATCH = 8               # older results are trimmed in batches, so the cut point (and the prompt cache) moves rarely
HEAD, TAIL = 900, 300   # characters kept from an older output
MIN_SAVING = 1500       # outputs shorter than this are left alone
REREAD_KEYS = {'read_file': 'path', 'web_fetch': 'url', 'list_files': 'path', 'search_files': 'query'}
STATE_HEADER = '[Working state from Luminaria. Added by the app, not part of the message above.]'


def _calls(messages):
    """tool_call_id -> (tool name, parsed arguments)."""
    found = {}
    for m in messages:
        for call in m.get('tool_calls') or []:
            fn = call.get('function') or {}
            try: args = json.loads(fn.get('arguments') or '{}')
            except (TypeError, ValueError): args = {}
            found[call.get('id')] = (fn.get('name') or '', args if isinstance(args, dict) else {})
    return found


def _reread_key(name, args):
    field = REREAD_KEYS.get(name)
    value = args.get(field) if field else None
    if not isinstance(value, str) or not value.strip(): return None
    return name, value.strip().replace('\\', '/').lower()


def _split(content):
    match = ACTION.match(content)
    return (match.group(1), content[match.end():]) if match else (None, content)


def shape(messages, keep_turns=KEEP_TURNS, keep_results=KEEP_RESULTS):
    """Return (messages, stats) for the conversation part of a request (no system message)."""
    out = [dict(m) for m in messages]
    stats = {'shortened': 0, 'superseded': 0, 'chars_saved': 0}
    users = [i for i, m in enumerate(out) if m.get('role') == 'user']
    boundary = users[-keep_turns] if len(users) >= keep_turns else 0
    calls = _calls(out)
    tools = [i for i, m in enumerate(out) if m.get('role') == 'tool']
    old_count = max(0, (len(tools) - keep_results) // BATCH * BATCH)
    old_by_count = set(tools[:old_count])

    newest = {}
    for i, m in enumerate(out):
        if m.get('role') != 'tool': continue
        key = _reread_key(*calls.get(m.get('tool_call_id'), ('', {})))
        if key: newest[key] = i

    for i, m in enumerate(out):
        content = m.get('content')
        if m.get('role') != 'tool' or not isinstance(content, str): continue
        action, body = _split(content)
        prefix = f'Action {action}: ' if action else ''
        pointer = f'history_read action_id={action}' if action else 'history_read'
        key = _reread_key(*calls.get(m.get('tool_call_id'), ('', {})))
        if key and newest.get(key, i) > i:
            replacement = prefix + f'[Superseded: this was read again later in the conversation. The newer copy is below. Earlier text: {pointer}.]'
            if len(replacement) < len(content):
                stats['superseded'] += 1; stats['chars_saved'] += len(content) - len(replacement)
                m['content'] = replacement
            continue
        if (i >= boundary and i not in old_by_count) or len(body) < MIN_SAVING: continue
        cut = len(body) - HEAD - TAIL
        replacement = (prefix + f'[Older output shortened to save context: {cut:,} of {len(body):,} characters hidden. Full text: {pointer}.]\n'
                       + body[:HEAD] + '\n…\n' + body[-TAIL:])
        if len(replacement) < len(content):
            stats['shortened'] += 1; stats['chars_saved'] += len(content) - len(replacement)
            m['content'] = replacement
    return out, stats


def attach_state(messages, parts):
    """Append working state to the last user or tool message; fall back to the system message."""
    parts = [p for p in parts if p]
    if not parts or not messages: return messages
    note = STATE_HEADER + '\n' + '\n\n'.join(parts)
    last = messages[-1]
    if last.get('role') in ('user', 'tool') and len(messages) > 1:
        content = last.get('content')
        if isinstance(content, str): last['content'] = content + '\n\n' + note
        elif isinstance(content, list): last['content'] = content + [{'type': 'text', 'text': note}]
        else: last['content'] = note
    else:
        messages[0]['content'] = messages[0]['content'] + '\n\n' + note
    return messages


def for_summary(transcript, head=1500, tail=500):
    """Trim long tool outputs before LLM compaction. The summary needs what a tool
    found, not every line of it, and fewer chunks means faster, steadier compaction.
    The full text stays on disk and is cited by action id."""
    out = []
    for m in transcript:
        content = m.get('content')
        if m.get('role') == 'tool' and isinstance(content, str) and len(content) > head + tail + 400:
            action, body = _split(content)
            prefix = f'Action {action}: ' if action else ''
            m = {**m, 'content': prefix + body[:head] + f'\n[… {len(body) - head - tail:,} characters omitted for the summary; full text: history_read action_id={action or "?"} …]\n' + body[-tail:]}
        out.append(m)
    return out
