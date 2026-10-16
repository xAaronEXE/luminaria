"""Curated GGUF catalog. Sizes and SHA256 values match publisher LFS records.

Nothing here is downloaded until the user chooses a quantization.
Abliteration is labeled as a third-party weight edit, not a quality claim.
"""
import re

BUDGET = 100 * 1024 ** 3
HEADROOM = 1024 ** 3

def quant(id, label, filename, size, digest, memory):
    return {'id':id,'label':label,'filename':filename,'bytes':size,'sha256':digest,'memory':memory}

def family(id, name, variant, parameters, purpose, description, strengths, repo, license, provenance, hardware, quants, caveat=''):
    return {'id':id,'name':name,'variant':variant,'parameters':parameters,'purpose':purpose,
            'description':description,'strengths':strengths,'context':32768,'vision':False,
            'repo':repo,'license':license,'provenance':provenance,'hardware':hardware,
            'caveat':caveat,'quants':quants}

ABLITERATED = ('Abliteration is a third-party weight edit intended to reduce refusals. '
               'It does not guarantee unrestricted answers, and it is not a coding or reasoning upgrade.')

CATALOG = [
 family('qwen3-8b','Qwen3 8B','standard','8.2B','General reasoning and writing',
        'Instruction-tuned Qwen3 model for conversation, reasoning, and tool use. Luminaria configures 32,768 tokens. Longer-context expansion is not enabled. This entry is not a measured recommendation.',
        ['Reasoning','Writing','Tools'],'Qwen/Qwen3-8B-GGUF','Apache-2.0, per the Qwen model card','Qwen/Qwen3-8B-GGUF',
        'Planning estimate only: about 8 GB for Q4_K_M, 10 GB for Q6_K, and 12 GB for Q8_0.',
        [quant('qwen3-8b-q4','Q4_K_M','Qwen3-8B-Q4_K_M.gguf',5027783488,'d98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785','About 8 GB'),
         quant('qwen3-8b-q6','Q6_K','Qwen3-8B-Q6_K.gguf',6725899040,'cb042ccd76795a8830d6be6bd4165245847cc68e41797b13bd61aed4c2cfbce6','About 10 GB'),
         quant('qwen3-8b-q8','Q8_0','Qwen3-8B-Q8_0.gguf',8709518112,'408b955510e196121c1c375201744783b5c9a43c7956d73fc78df54c66e883d6','About 12 GB')]),
 family('qwen3-4b','Qwen3 4B','standard','4B','Lighter general model',
        'Smaller Qwen3 instruction model for machines with less memory. Configured context is 32,768 tokens. Speed and answer quality are unmeasured until you benchmark it on this PC.',
        ['Reasoning','Writing'],'Qwen/Qwen3-4B-GGUF','Apache-2.0, per the Qwen model card','Qwen/Qwen3-4B-GGUF',
        'Planning estimate only: about 6 GB for Q4_K_M and 8 GB for Q8_0.',
        [quant('qwen3-4b-q4','Q4_K_M','Qwen3-4B-Q4_K_M.gguf',2497280256,'7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5','About 6 GB'),
         quant('qwen3-4b-q8','Q8_0','Qwen3-4B-Q8_0.gguf',4280404704,'8c2f07f26af9747e41988551106f149b03eb9b5cb6df636027b6bf6278473300','About 8 GB')]),
 family('qwen25-coder-7b','Qwen2.5 Coder 7B','standard','7.6B','Coding and tool use',
        'Instruction-tuned Qwen2.5 Coder model in a single GGUF file. Configured context is 32,768 tokens. A speed benchmark does not score coding quality.',
        ['Coding','Tools'],'Qwen/Qwen2.5-Coder-7B-Instruct-GGUF','Apache-2.0, per the Qwen model card','Qwen/Qwen2.5-Coder-7B-Instruct-GGUF',
        'Planning estimate only: about 8 GB for Q4_K_M, 10 GB for Q6_K, and 12 GB for Q8_0.',
        [quant('qwen25-coder-7b-q4','Q4_K_M','qwen2.5-coder-7b-instruct-q4_k_m.gguf',4683073536,'509287f78cb4d4cf6b3843734733b914b2c158e43e22a7f4bf5e963800894d3c','About 8 GB'),
         quant('qwen25-coder-7b-q6','Q6_K','qwen2.5-coder-7b-instruct-q6_k.gguf',6254198784,'46291ddea1bfb608fe63d9a1907eea6918bda87a7626593edc4bf97c5fd73f9d','About 10 GB'),
         quant('qwen25-coder-7b-q8','Q8_0','qwen2.5-coder-7b-instruct-q8_0.gguf',8098525184,'b36a4e1c3ddf2ba6fd5501b926128e5fc6430881caaff07e9629bd18f06f685f','About 12 GB')]),
 family('qwen25-coder-3b','Qwen2.5 Coder 3B','standard','3.1B','Lighter coding model',
        'Smaller Qwen2.5 Coder instruction model for tighter memory. Configured context is 32,768 tokens. Not measured on this PC until you benchmark it.',
        ['Coding'],'Qwen/Qwen2.5-Coder-3B-Instruct-GGUF','Apache-2.0, per the Qwen model card','Qwen/Qwen2.5-Coder-3B-Instruct-GGUF',
        'Planning estimate only: about 4 GB for Q4_K_M and 6 GB for Q8_0.',
        [quant('qwen25-coder-3b-q4','Q4_K_M','qwen2.5-coder-3b-instruct-q4_k_m.gguf',2104932800,'724fb256bec1ff062b2f65e4569e871ad2e95ab2a3989723d1769c54294730b7','About 4 GB'),
         quant('qwen25-coder-3b-q8','Q8_0','qwen2.5-coder-3b-instruct-q8_0.gguf',3616088512,'f648c25dfd5a0870c4ad76724a745124ab5667ff97b664534fcbe46089b75ab8','About 6 GB')]),
 family('qwen25-coder-7b-abliterated','Qwen2.5 Coder 7B Abliterated','abliterated','7.6B','Coding weights with abliteration',
        'Bartowski GGUF quantization of huihui-ai’s abliterated Qwen2.5 Coder 7B Instruct weights. Configured context is 32,768 tokens.',
        ['Coding','Tools'],'bartowski/Qwen2.5-Coder-7B-Instruct-abliterated-GGUF','Base model card is Apache-2.0. These files are a third-party abliterated quantization.',
        'huihui-ai/Qwen2.5-Coder-7B-Instruct-abliterated, quantized by bartowski',
        'Planning estimate only: about 8 GB for Q4_K_M, 10 GB for Q6_K, and 12 GB for Q8_0.',
        [quant('qwen25-coder-7b-abliterated-q4','Q4_K_M','Qwen2.5-Coder-7B-Instruct-abliterated-Q4_K_M.gguf',4683074400,'fdf02c16fb654ff60b2c30f1e91573ebc603a7084df3449df89120dca2b18170','About 8 GB'),
         quant('qwen25-coder-7b-abliterated-q6','Q6_K','Qwen2.5-Coder-7B-Instruct-abliterated-Q6_K.gguf',6254199648,'16ba964743fe4bd3b45c5e562039795fa2ead1ae33dbb637632a25316b9e3f7a','About 10 GB'),
         quant('qwen25-coder-7b-abliterated-q8','Q8_0','Qwen2.5-Coder-7B-Instruct-abliterated-Q8_0.gguf',8098526048,'bc1a0cb02f5669e4f7068e9153d75d3239b09f91eb77e7c9ab83ddeef55d2b93','About 12 GB')],
        ABLITERATED),
 family('qwen25-7b-abliterated','Qwen2.5 7B Abliterated','abliterated','7.6B','General weights with abliteration',
        'mradermacher GGUF quantization of an abliterated Qwen2.5 7B Instruct model. Configured context is 32,768 tokens.',
        ['Writing','Reasoning'],'mradermacher/Qwen2.5-7B-Instruct-abliterated-GGUF','Base model card is Apache-2.0. These files are a third-party abliterated quantization.',
        'Abliterated Qwen2.5-7B-Instruct, quantized by mradermacher',
        'Planning estimate only: about 8 GB for Q4_K_M, 10 GB for Q6_K, and 12 GB for Q8_0.',
        [quant('qwen25-7b-abliterated-q4','Q4_K_M','Qwen2.5-7B-Instruct-abliterated.Q4_K_M.gguf',4683074560,'72a55f16d3fe3647f5e4bd4a59bd3db000cc61f0e050f51993176e5bcbf0f93c','About 8 GB'),
         quant('qwen25-7b-abliterated-q6','Q6_K','Qwen2.5-7B-Instruct-abliterated.Q6_K.gguf',6254199808,'4684dec06acd61d6b62c70993283a4a3a5544da05569463559e9bbaffa332df2','About 10 GB'),
         quant('qwen25-7b-abliterated-q8','Q8_0','Qwen2.5-7B-Instruct-abliterated.Q8_0.gguf',8098526208,'6282e34f35e75770972582049b48a6b20e03fc2b7492404db2f32aa5e8a6b88c','About 12 GB')],
        ABLITERATED),
 family('qwen25-coder-14b-abliterated','Qwen2.5 Coder 14B Abliterated','abliterated','14.7B','Larger coding weights with abliteration',
        'Bartowski GGUF quantization of an abliterated Qwen2.5 Coder 14B Instruct model. It needs substantially more memory and disk than the 7B files. Configured context is 32,768 tokens.',
        ['Coding','Tools'],'bartowski/Qwen2.5-Coder-14B-Instruct-abliterated-GGUF','Base model card is Apache-2.0. These files are a third-party abliterated quantization.',
        'Abliterated Qwen2.5-Coder-14B-Instruct, quantized by bartowski',
        'Planning estimate only: about 12 GB for Q4_K_M and 16 GB for Q6_K.',
        [quant('qwen25-coder-14b-abliterated-q4','Q4_K_M','Qwen2.5-Coder-14B-Instruct-abliterated-Q4_K_M.gguf',8988111200,'e89a7ae4e2b456bf33c75cff35664751df20ff273e551d7cf7640aa9e84d3b79','About 12 GB'),
         quant('qwen25-coder-14b-abliterated-q6','Q6_K','Qwen2.5-Coder-14B-Instruct-abliterated-Q6_K.gguf',12124684640,'341f5d4db35978331e7f2bfde3871d76b7c856bb5279ffaed19616092ec79e69','About 16 GB')],
        ABLITERATED),
]

def validate():
    ids, files = set(), set()
    if not CATALOG: raise ValueError('Model catalog is empty')
    for entry in CATALOG:
        if entry['variant'] not in ('standard','abliterated'): raise ValueError('Invalid catalog variant')
        if entry['id'] in ids or not re.fullmatch(r'[a-z0-9-]{1,60}', entry['id']): raise ValueError('Invalid catalog id')
        ids.add(entry['id'])
        if not re.fullmatch(r'[A-Za-z0-9._-]+/[A-Za-z0-9._-]+', entry['repo']): raise ValueError('Invalid catalog repository')
        for item in entry['quants']:
            if item['id'] in ids or not re.fullmatch(r'[a-z0-9-]{1,60}', item['id']): raise ValueError('Invalid quantization id')
            if item['filename'] in files or not re.fullmatch(r'[A-Za-z0-9._-]{1,180}\.gguf', item['filename']): raise ValueError('Invalid catalog filename')
            if item['bytes'] <= 0 or not re.fullmatch(r'[a-f0-9]{64}', item['sha256']): raise ValueError('Invalid catalog file record')
            ids.add(item['id']); files.add(item['filename'])

validate()
