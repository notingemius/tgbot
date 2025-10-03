# test_llm_perf.py
import time
from llama_cpp import Llama

MODEL = "models\\q4_0-orca-mini-3b.gguf"   # поправь путь если нужно

def main():
    print("Loading model:", MODEL)
    t0 = time.time()
    mdl = Llama(model_path=MODEL, n_ctx=256)  # n_ctx поменьше для теста
    print("Loaded in", time.time() - t0, "s")
    prompt = "Привет, как дела."
    print("Prompt:", prompt)
    t1 = time.time()
    # параметры: max_tokens небольшое
    out = mdl(prompt, max_tokens=80, temperature=0.2)
    t2 = time.time()
    # try to extract text (llama_cpp may return dict-like)
    if isinstance(out, dict) and "choices" in out:
        text = out["choices"][0].get("text", "")
    else:
        text = str(out)
    print("Response time:", round(t2 - t1,2), "s")
    print("Response:\n", text)

if __name__ == "__main__":
    main()
