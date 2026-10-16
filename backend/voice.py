"""Offline speech. Audio stays in RAM; only the accepted transcript enters chat."""
import io, threading, wave, time
from .config import BASE_DATA

FOLDER = BASE_DATA / 'voice'
STT = FOLDER / 'whisper-base.en'
VOICE = FOLDER / 'en_US-lessac-medium.onnx'
_recognizer = None
_speaker = None
_speaker_id = None
VOICES={
 'lessac':{'name':'Lessac','character':'Female · US English','quality':'Medium','path':'en/en_US/lessac/medium','file':'en_US-lessac-medium'},
 'amy':{'name':'Amy','character':'Female · US English','quality':'Medium','path':'en/en_US/amy/medium','file':'en_US-amy-medium'},
 'ryan':{'name':'Ryan','character':'Male · US English','quality':'High','path':'en/en_US/ryan/high','file':'en_US-ryan-high'},
}

def voice_path(id):
    if id not in VOICES: raise ValueError('Unknown voice')
    return FOLDER/(VOICES[id]['file']+'.onnx')

def voice_catalog():
    return [{'id':id,**v,'installed':voice_path(id).exists() and voice_path(id).with_suffix('.onnx.json').exists()} for id,v in VOICES.items()]

def install_voice(id):
    import shutil
    from huggingface_hub import hf_hub_download
    p=voice_path(id);v=VOICES[id];FOLDER.mkdir(parents=True,exist_ok=True)
    for suffix in ('.onnx','.onnx.json'):
        source=hf_hub_download('rhasspy/piper-voices',v['path']+'/'+v['file']+suffix)
        target=FOLDER/(v['file']+suffix); temp=target.with_suffix(target.suffix+'.tmp');shutil.copyfile(source,temp);temp.replace(target)
    card=hf_hub_download('rhasspy/piper-voices',v['path']+'/MODEL_CARD')
    shutil.copyfile(card,FOLDER/(v['file']+'-MODEL_CARD.md'))
    return {'voices':voice_catalog()}
_stt_lock = threading.Lock()
_tts_lock = threading.Lock()

def status():
    return {'ready': all((STT/f).exists() for f in ['model.bin','config.json','tokenizer.json','vocabulary.txt']) and VOICE.exists() and VOICE.with_suffix('.onnx.json').exists(),
            'recognition':'Whisper base.en · CPU INT8', 'speech':'Piper Lessac · CPU',
            'local':True, 'audio_saved':False,'voices':voice_catalog()}

def install_models():
    import shutil
    from huggingface_hub import snapshot_download,hf_hub_download
    FOLDER.mkdir(parents=True,exist_ok=True)
    snapshot_download('Systran/faster-whisper-base.en',local_dir=STT,
        allow_patterns=['model.bin','config.json','tokenizer.json','vocabulary.txt'])
    for name in ['en_US-lessac-medium.onnx','en_US-lessac-medium.onnx.json','MODEL_CARD']:
        path=hf_hub_download('rhasspy/piper-voices','en/en_US/lessac/medium/'+name)
        shutil.copyfile(path,FOLDER/('PIPER_MODEL_CARD' if name=='MODEL_CARD' else name))
    return status()

def transcribe(raw):
    global _recognizer
    if not status()['ready']: raise ValueError('Voice models are not installed. Run setup_voice.py first.')
    with wave.open(io.BytesIO(raw),'rb') as w:
        if w.getnchannels()!=1 or w.getsampwidth()!=2 or w.getframerate()!=16000:
            raise ValueError('Voice input must be mono 16 kHz PCM16 WAV')
        if w.getnframes()>16000*35: raise ValueError('Keep each voice turn under 35 seconds')
        import numpy as np
        samples=np.frombuffer(w.readframes(w.getnframes()),dtype=np.int16).astype(np.float32)/32768.
    start=time.monotonic()
    with _stt_lock:
        if _recognizer is None:
            from faster_whisper import WhisperModel
            _recognizer=WhisperModel(str(STT),device='cpu',compute_type='int8',cpu_threads=4,local_files_only=True)
        segments,_=_recognizer.transcribe(samples,language='en',beam_size=1,vad_filter=True,condition_on_previous_text=False)
        text=' '.join(s.text.strip() for s in segments if s.no_speech_prob<.7).strip()
    return {'text':text,'seconds':round(time.monotonic()-start,3)}

def synthesize(text,voice_id='lessac'):
    global _speaker,_speaker_id
    text=str(text).strip()
    if not text or len(text)>1600: raise ValueError('Speech requires 1–1600 characters')
    path=voice_path(voice_id)
    if not path.exists(): raise ValueError('Download this voice in Voice settings first')
    with _tts_lock:
        if _speaker is None or _speaker_id!=voice_id:
            from piper import PiperVoice
            _speaker=PiperVoice.load(str(path));_speaker_id=voice_id
        out=io.BytesIO()
        with wave.open(out,'wb') as wav: _speaker.synthesize_wav(text,wav)
        return out.getvalue()
