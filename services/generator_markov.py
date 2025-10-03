# services/generator_markov.py
import random
from collections import defaultdict
import re

class MarkovGenerator:
    def __init__(self, order: int = 2):
        self.order = order
        self.model = defaultdict(list)
        self._starters = []

    def feed(self, text: str):
        tokens = self._tokenize(text)
        if len(tokens) <= self.order:
            return
        for i in range(len(tokens) - self.order):
            key = tuple(tokens[i:i+self.order])
            self.model[key].append(tokens[i+self.order])
            if i == 0:
                self._starters.append(key)

    def _tokenize(self, text: str):
        # simple tokenizer (preserves punctuation)
        return re.findall(r"\\w+|[.,!?;]", text)

    def generate(self, max_words: int = 50) -> str:
        if not self.model:
            return ""
        import random
        key = random.choice(self._starters) if self._starters else random.choice(list(self.model.keys()))
        words = list(key)
        for _ in range(max_words):
            choices = self.model.get(tuple(words[-self.order:]), None)
            if not choices:
                break
            nxt = random.choice(choices)
            words.append(nxt)
        return " ".join(words).replace(" ,", ",").replace(" .", ".")

# helper: build generator from documents
def build_markov_from_docs(docs):
    mg = MarkovGenerator(order=2)
    for d in docs:
        mg.feed(d.get("content",""))
    return mg
