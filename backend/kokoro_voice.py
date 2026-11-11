"""Offline English Kokoro synthesis with the packaged eSpeak phonemizer."""

import io
import json
import wave


class KokoroVoice:
    sample_rate = 24000

    def __init__(self, folder):
        import numpy as np
        import onnxruntime as ort
        from piper.phonemize_espeak import EspeakPhonemizer

        options = ort.SessionOptions()
        options.intra_op_num_threads = 4
        self.session = ort.InferenceSession(str(folder / 'kokoro-v1.0.int8.onnx'),
                                            sess_options=options, providers=['CPUExecutionProvider'])
        with np.load(folder / 'voices-v1.0.bin', allow_pickle=False) as voices:
            self.voice = voices['af_heart'].copy()
        self.vocab = json.loads((folder / 'kokoro-config.json').read_text(encoding='utf-8'))['vocab']
        self.phonemizer = EspeakPhonemizer()

    def synthesize(self, text):
        import numpy as np

        out = io.BytesIO()
        with wave.open(out, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wrote_audio = False
            for sentence in self.phonemizer.phonemize('en-us', text):
                tokens = [self.vocab[phoneme] for phoneme in sentence if phoneme in self.vocab]
                for offset in range(0, len(tokens), 450):
                    chunk = tokens[offset:offset + 450]
                    if wrote_audio:
                        wav.writeframes(b'\0\0' * (self.sample_rate // 8))
                    result, *_ = self.session.run(None, {
                        'input_ids': np.array([[0, *chunk, 0]], dtype=np.int64),
                        'style': self.voice[len(chunk) - 1],
                        'speed': np.ones(1, dtype=np.float32),
                    })
                    pcm = (np.clip(result.ravel(), -1.0, 1.0) * 32767).astype('<i2')
                    wav.writeframes(pcm.tobytes())
                    wrote_audio = True
            if not wrote_audio:
                raise ValueError('The voice could not pronounce any of this text.')
        return out.getvalue()
