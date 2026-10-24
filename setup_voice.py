"""One-time local voice model download; no account or audio upload."""
import os
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING']='1'
from huggingface_hub import snapshot_download, hf_hub_download
from backend.voice import FOLDER,STT
FOLDER.mkdir(parents=True,exist_ok=True)
snapshot_download('Systran/faster-whisper-base.en',local_dir=STT,
                  allow_patterns=['model.bin','config.json','tokenizer.json','vocabulary.json','vocabulary.txt','preprocessor_config.json'])
for name in ['en_US-lessac-medium.onnx','en_US-lessac-medium.onnx.json','MODEL_CARD']:
    p=hf_hub_download('rhasspy/piper-voices','en/en_US/lessac/medium/'+name)
    import shutil
    shutil.copyfile(p,FOLDER/('PIPER_MODEL_CARD' if name=='MODEL_CARD' else name))
print('Offline voice models installed:',FOLDER)

