"""Validated, profile-local presentation and voice preferences."""
import re

COLOR_KEYS = {'bg','sidebar','panel','raised','hover','line','text','muted','dim','accent','accent-dark','glow','warning','danger'}
DEFAULTS = {'theme_mode': 'light', 'theme': 'Graphite & Ivory', 'background': '#141A17', 'accent': '#EAE6D9', 'colors': {},
            'motion': True, 'metrics': True, 'microphone': '', 'voice_rate': 1.0,
            'voice_threshold': 0.022, 'voice_silence': 0.85, 'interruptible': True,
            'saved_themes': [], 'voice_id':'lessac',
            'appearance': {'mode':'light','accent':'','modes':{'dark':{},'light':{}},'version':1}}
APPEARANCE_KEYS = {'bg','sidebar','panel','raised','hover','line','control-line','text','muted','dim','success','warning','danger','info','entity','particle','lattice','pathway','glow'}
HEX = re.compile(r'#[0-9a-fA-F]{6}')

def appearance(value):
    if not isinstance(value, dict) or set(value)-{'mode','accent','modes','version'}: raise ValueError('Invalid appearance settings')
    if value.get('mode','light') not in ('dark','light','system'): raise ValueError('Choose light, dark or follow system')
    accent = value.get('accent','')
    if not (accent=='' or (isinstance(accent,str) and HEX.fullmatch(accent))): raise ValueError('Use a six-digit hex accent, or none')
    modes = value.get('modes',{})
    if not isinstance(modes, dict) or set(modes)-{'dark','light'}: raise ValueError('Appearance modes are dark and light')
    for mode in modes.values():
        if not isinstance(mode, dict) or set(mode)-{'accent','colors'}: raise ValueError('Invalid mode appearance')
        if mode.get('accent') is not None and not (isinstance(mode['accent'],str) and HEX.fullmatch(mode['accent'])): raise ValueError('Use a six-digit hex accent')
        colors = mode.get('colors',{})
        if not isinstance(colors, dict) or set(colors)-APPEARANCE_KEYS: raise ValueError('Unknown appearance color')
        if not all(isinstance(c,str) and HEX.fullmatch(c) for c in colors.values()): raise ValueError('Use six-digit hex colors')
    return {'mode':value.get('mode','light'),'accent':accent,'modes':{m:modes.get(m,{}) for m in ('dark','light')},'version':1}

def migrate(stored):
    """An explicitly saved dark or light choice carries over; otherwise the default is light.
    The legacy custom palette was not applied in 0.2.7 and stays unapplied."""
    if 'appearance' in stored: return stored
    mode=stored.get('theme_mode') if stored.get('theme_mode') in ('dark','light') else 'light'
    return {**stored,'appearance':{**DEFAULTS['appearance'],'mode':mode}}

def validate(body):
    out = {}
    for key, value in body.items():
        if key not in DEFAULTS: raise ValueError('Unknown preference: '+key)
        if key=='theme_mode':
            if value not in ('dark','light','system'): raise ValueError('Choose light, dark or follow system')
        elif key=='appearance':
            value=appearance(value)
        elif key=='voice_id':
            from .voice import VOICES
            if value not in VOICES: raise ValueError('Unknown voice')
        elif key == 'colors':
            if not isinstance(value, dict) or set(value)-COLOR_KEYS: raise ValueError('Unknown palette color')
            for color in value.values():
                if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color): raise ValueError('Use a six-digit hex color')
        elif key in ('background', 'accent'):
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value): raise ValueError('Use a six-digit hex color')
        elif key in ('motion', 'metrics', 'interruptible'):
            if not isinstance(value, bool): raise ValueError('Boolean preference required')
        elif key in ('voice_rate', 'voice_threshold', 'voice_silence'):
            lo, hi = {'voice_rate': (.65, 1.5), 'voice_threshold': (.008, .08), 'voice_silence': (.4, 2)}[key]
            value = float(value)
            if not lo <= value <= hi: raise ValueError('Voice preference outside supported range')
        elif key == 'saved_themes':
            if not isinstance(value, list) or len(value)>30: raise ValueError('Save up to 30 themes')
            for theme in value:
                if not isinstance(theme,dict) or not {'theme','background','accent'} <= set(theme) or set(theme)-{'theme','background','accent','colors'}: raise ValueError('Invalid saved theme')
                validate(theme)
        elif not isinstance(value, str) or len(value)>200: raise ValueError('Preference text too long')
        out[key] = value
    return out
