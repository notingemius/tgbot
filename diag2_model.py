# diag2_model.py
import os, traceback
from gpt4all import GPT4All
from config import MODELS_DIR, MODEL_NAME

def info(msg):
    print(msg)

model_path = os.path.abspath(MODELS_DIR)
full_file = os.path.join(model_path, MODEL_NAME)

info("MODEL_PATH: " + model_path)
info("EXPECTED FILE: " + full_file)
info("Exists: " + str(os.path.exists(full_file)))
if os.path.exists(full_file):
    info("Size (MB): {:.2f}".format(os.path.getsize(full_file) / 1024 / 1024))
    with open(full_file, "rb") as f:
        head = f.read(8)
    info("Header bytes: " + repr(head))

info("\nПопытка загрузки с GPT4All(model_name=..., model_path=..., allow_download=False):")
try:
    m = GPT4All(model_name=MODEL_NAME, model_path=model_path, allow_download=False)
    info("OK: модель загружена (model_name+model_path, allow_download=False)")
except Exception as e:
    info("ERROR: " + repr(e))
    info(traceback.format_exc())

info("\nПопытка загрузки позиционно (GPT4All(full_file)):")
try:
    m2 = GPT4All(full_file)
    info("OK: модель загружена (positional)")
except Exception as e:
    info("ERROR: " + repr(e))
    info(traceback.format_exc())

print("\nГотово.")
