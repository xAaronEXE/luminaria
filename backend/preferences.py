"""Validated, profile-local presentation and voice preferences."""
import re

DEFAULTS = {'theme': 'Acid mint', 'background': '#141A17', 'accent': '#B7FF2E',
            'motion': True, 'metrics': True, 'microphone': '', 'voice_rate': 1.0,
            'voice_threshold': 0.022, 'voice_silence': 0.85, 'interruptible': True,
            'saved_themes': [], 'voice_id':'lessac'}

def validate(body):
    out = {}
    for key, value in body.items():
        if key not in DEFAULTS: raise ValueError('Unknown preference: '+key)
        if key=='voice_id':
            from .voice import VOICES
            if value not in VOICES: raise ValueError('Unknown voice')
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
                if set(theme) != {'theme','background','accent'}: raise ValueError('Invalid saved theme')
                validate(theme)
        elif not isinstance(value, str) or len(value)>200: raise ValueError('Preference text too long')
        out[key] = value
    return out
