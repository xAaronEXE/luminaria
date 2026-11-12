"""Choose a request lane before the first model call."""

import re


_GREETING = re.compile(r'(?:hi|hello|hey|good (?:morning|afternoon|evening)|thanks|thank you)[.! ]*', re.I)
_PLAN = re.compile(r'^(?:please )?(?:plan (?:how|a |the |this |my )|(?:make|draft|write|create) (?:me )?a plan\b)', re.I)
_RESEARCH = re.compile(r'^(?:please )?(?:research\b|look up\b|search (?:the web|online)\b|find (?:sources|references)\b)', re.I)
_REVIEW = re.compile(r'^(?:please )?(?:wipe\b|factory reset\b|(?:uninstall|deploy|publish)\b|send (?:an? |the )?(?:email|message)\b)', re.I)
_EXECUTE = re.compile(r'\b(?:then|and)\s+(?:apply|build|create|delete|deploy|edit|implement|install|publish|run|send|write)\b', re.I)
_CHANGE = re.compile(r'^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:fix|patch|implement|apply|edit|modify|delete|rename|move|copy|install|run|execute|deploy|publish)\s+\S|^(?:please\s+)?(?:create|write|save|build)\s+[^\n]*(?:\b(?:file|folder|installer|release|project)\b|\.[a-z0-9]{1,8}\b)', re.I)
_INSPECT = re.compile(r'^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:inspect|read|open|list|search|scan|look through|look at)\s+(?:[^\n]*\b(?:file|files|folder|directory|workspace|repository)\b|[^\s]+\.[a-z0-9]{1,8}\b)', re.I)


def action_intent(text):
    """Recognize clear requests for tool work without treating every chat as a task."""
    if _CHANGE.match(text): return 'change'
    if _INSPECT.match(text): return 'inspect'
    return None


_DEFINITION = re.compile(r'^(?:what is an? |what does .+ mean[?!. ]*$|define )', re.I)
_CONTEXT = re.compile(r'\b(?:today|current|latest|attached|this (?:file|project|app|code)|my )\b', re.I)


def classify(content, *, spoken=False):
    """Route clear intents. Mixed or ambiguous messages retain ordinary execution."""
    if not isinstance(content, str):
        return 'do'
    text = content.strip()
    if _GREETING.fullmatch(text):
        return 'answer'
    if _REVIEW.match(text) or (_PLAN.match(text) and not _EXECUTE.search(text)):
        return 'plan'
    if _RESEARCH.match(text) and not _EXECUTE.search(text):
        return 'research'
    if spoken and len(text)<=120 and _DEFINITION.match(text) and not (_CONTEXT.search(text) or _EXECUTE.search(text)):
        return 'answer'
    return 'do'
