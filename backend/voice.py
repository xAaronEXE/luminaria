"""Offline speech. Audio stays in RAM; only the accepted transcript enters chat."""
import io, threading, wave, time
from .config import BASE_DATA

FOLDER = BASE_DATA / 'voice'
STT = FOLDER / 'whisper-base.en'
VOICE = FOLDER / 'en_US-lessac-medium.onnx'
_recognizer = None
_speaker = None
_speaker_id = None
_kokoro = None
VOICES={
 'kokoro-heart':{'name':'Heart (Kokoro)','character':'Female · US English','quality':'Neural','file':'kokoro-v1.0.int8'},
 'lessac':{'name':'Lessac','character':'Female · US English','quality':'Medium','path':'en/en_US/lessac/medium','file':'en_US-lessac-medium'},
 'amy':{'name':'Amy','character':'Female · US English','quality':'Medium','path':'en/en_US/amy/medium','file':'en_US-amy-medium'},
 'ryan':{'name':'Ryan','character':'Male · US English','quality':'High','path':'en/en_US/ryan/high','file':'en_US-ryan-high'},
}

def voice_path(id):
    if id not in VOICES: raise ValueError('Unknown voice')
    return FOLDER/(VOICES[id]['file']+'.onnx')

def voice_installed(ident):
    if ident == 'kokoro-heart':
        from .voice_assets import ASSETS
        return all((FOLDER / asset['name']).is_file() for asset in ASSETS[ident])
    path=voice_path(ident)
    return path.is_file() and path.with_suffix('.onnx.json').is_file()


def voice_catalog():
    return [{'id':ident,**voice,'installed':voice_installed(ident)} for ident,voice in VOICES.items()]

_download_lock = threading.Lock()

def _install_assets(ident,folder):
    import hashlib,os,shutil,uuid
    import httpx
    from .voice_assets import ASSETS
    assets=ASSETS[ident];folder.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(folder).free < sum(item['bytes'] for item in assets)+128*1024**2:
        raise ValueError('Not enough disk space for voice models. Free some space and try again.')
    def digest(path):
        h=hashlib.sha256()
        with path.open('rb') as f:
            while chunk:=f.read(1024*1024):h.update(chunk)
        return h.hexdigest()
    for item in assets:
        target=folder/(ident+'-MODEL_CARD.md' if item['name']=='MODEL_CARD' else item['name'])
        if target.is_file() and target.stat().st_size==item['bytes'] and digest(target)==item['sha256']:continue
        temp=target.with_name(target.name+'.'+uuid.uuid4().hex+'.part')
        try:
            with httpx.Client(timeout=httpx.Timeout(60,connect=20),follow_redirects=True) as client:
                with client.stream('GET',item['url'],headers={'User-Agent':'Luminaria voice setup'}) as response:
                    response.raise_for_status();h=hashlib.sha256();size=0
                    with temp.open('wb') as out:
                        for chunk in response.iter_bytes(1024*1024):
                            size+=len(chunk)
                            if size>item['bytes']:raise ValueError('The voice download did not match the publisher. Please retry.')
                            h.update(chunk);out.write(chunk)
            if size!=item['bytes'] or h.hexdigest()!=item['sha256']:
                raise ValueError('The voice download was incomplete or failed its checksum. Please retry.')
            os.replace(temp,target)
        except httpx.HTTPStatusError as error:
            raise ValueError('The voice publisher returned HTTP '+str(error.response.status_code)+'. Please try again later.') from error
        except httpx.HTTPError as error:
            raise ValueError('Could not download the voice model. Check your connection, firewall or proxy, then retry.') from error
        except OSError as error:
            raise ValueError('Could not save the voice model. Check free disk space and folder permissions, then retry.') from error
        finally:temp.unlink(missing_ok=True)

def install_voice(id):
    voice_path(id) # Validate before downloading anything.
    with _download_lock:_install_assets(id,FOLDER)
    return {'voices':voice_catalog()}
_stt_lock = threading.Lock()
_tts_lock = threading.Lock()

def status():
    return {'ready': all((STT/f).exists() for f in ['model.bin','config.json','tokenizer.json','vocabulary.txt']) and VOICE.exists() and VOICE.with_suffix('.onnx.json').exists(),
            'recognition':'Whisper base.en · CPU INT8', 'speech':'Piper or Kokoro · CPU',
            'local':True, 'audio_saved':False,'voices':voice_catalog()}

def install_models():
    with _download_lock:
        _install_assets('whisper',STT)
        _install_assets('lessac',FOLDER)
    return status()

def transcribe(raw):
    global _recognizer
    if not status()['ready']: raise ValueError('Voice models are not installed. Download voice models in Voice settings first.')
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
    global _speaker,_speaker_id,_kokoro
    text=str(text).strip()
    if not text or len(text)>1600: raise ValueError('Speech requires 1–1600 characters')
    path=voice_path(voice_id)
    if not voice_installed(voice_id): raise ValueError('Download this voice in Voice settings first')
    with _tts_lock:
        if voice_id=='kokoro-heart':
            if _kokoro is None:
                from .kokoro_voice import KokoroVoice
                _kokoro=KokoroVoice(FOLDER)
            return _kokoro.synthesize(text)
        if _speaker is None or _speaker_id!=voice_id:
            from piper import PiperVoice
            _speaker=PiperVoice.load(str(path));_speaker_id=voice_id
        out=io.BytesIO()
        with wave.open(out,'wb') as wav: _speaker.synthesize_wav(text,wav)
        return out.getvalue()
