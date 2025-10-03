# test_gpt4all.py
from gpt4all import GPT4All
m = GPT4All(model_name="orca-mini-3b.gguf", model_path="models")  # имя/путь подставь свой
print(m.generate("Привет! Представься коротко.", max_tokens=120))
