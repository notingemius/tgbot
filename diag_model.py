import os
from gpt4all import GPT4All

MODEL = "models/Phi-3.1-mini-128k-instruct-Q4_0.gguf"
model_path = os.path.abspath(MODEL)

print("Model path:", model_path)
print("Exists:", os.path.exists(model_path))
if os.path.exists(model_path):
    print("Size (bytes):", os.path.getsize(model_path))

print("\nПопытка загрузки через GPT4All():")
try:
    m = GPT4All(model_path)  # пробуем как позиционный аргумент
    print("Loaded OK (positional).")
except Exception as e:
    print("Error (positional):", repr(e))

print("\nПопытка загрузки через GPT4All(model_name=...):")
try:
    m = GPT4All(model_name=model_path)  # пробуем второй вариант
    print("Loaded OK (model_name).")
except Exception as e:
    print("Error (model_name):", repr(e))
