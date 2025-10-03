# test_llm.py
from pathlib import Path
import os
# optionally tune threads:
os.environ.setdefault("OMP_NUM_THREADS", "4")  # подбери под свою CPU: 2,4,8...
try:
    from llama_cpp import Llama
except Exception as e:
    print("ERROR: cannot import llama_cpp:", e)
    raise SystemExit(1)

model_path = Path("models/q4_0-orca-mini-3b.gguf")
if not model_path.exists():
    print("Model file not found:", model_path.resolve())
    raise SystemExit(2)

print("Loading model:", model_path)
# устанавливаем n_ctx явно (взвесь память): 512/1024/2048 — чем больше, тем больше памяти
llm = Llama(model_path=str(model_path), n_ctx=1024)  

prompt = "Привет! Кратко представься и скажи, как создать заметку в боте."
print("Generating...")
resp = llm(prompt, max_tokens=150, temperature=0.2)
# обработка результата
out = None
if isinstance(resp, dict) and "choices" in resp and resp["choices"]:
    # new-style dict
    out = resp["choices"][0].get("text") or resp["choices"][0].get("message") or str(resp["choices"][0])
else:
    out = str(resp)
print("=== RAW OUTPUT (repr) ===")
print(repr(out))
print("=== FORMATTED OUTPUT ===")
print(out.strip())
