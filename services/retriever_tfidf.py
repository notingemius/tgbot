# services/retriever_tfidf.py
import os
import sqlite3
from typing import List, Dict, Tuple
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import joblib

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "bot.db")
MODELS_DIR = os.path.join(BASE_DIR, "models")
INDEX_FILE = os.path.join(MODELS_DIR, "tfidf_index.joblib")  # stores {'vectorizer', 'tfidf_matrix', 'doc_ids'}

def _conn():
    return sqlite3.connect(DB_PATH)

def init_tables():
    conn = _conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT,
        created_at TEXT
    );
    """)
    conn.commit()
    conn.close()

def add_document(title: str, content: str, created_at: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO documents (title, content, created_at) VALUES (?, ?, ?)", (title, content, created_at))
    rowid = cur.lastrowid
    conn.commit()
    conn.close()
    return rowid

def list_documents(limit: int = 1000) -> List[Dict]:
    conn = _conn()
    cur = conn.cursor()
    cur.execute("SELECT id, title, content FROM documents ORDER BY id DESC LIMIT ?", (limit,))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "content": r[2]} for r in rows]

def rebuild_index():
    """Собрать TF-IDF индекс заново (читает все documents из БД)."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    docs = list_documents(limit=10000)
    texts = [d["content"] for d in docs]
    if not texts:
        # сохраняем пустой структуру
        joblib.dump({"vectorizer": None, "tfidf": None, "doc_ids": []}, INDEX_FILE)
        return
    vectorizer = TfidfVectorizer(ngram_range=(1,2), max_features=50000)
    tfidf = vectorizer.fit_transform(texts)
    doc_ids = [d["id"] for d in docs]
    joblib.dump({"vectorizer": vectorizer, "tfidf": tfidf, "doc_ids": doc_ids}, INDEX_FILE)

def _load_index():
    if not os.path.exists(INDEX_FILE):
        return None
    return joblib.load(INDEX_FILE)

def search(query: str, top_k: int = 5) -> List[Dict]:
    """Ищет релевантные документы и возвращает список dicts (id,title,content,score)."""
    idx = _load_index()
    if not idx or idx.get("vectorizer") is None:
        return []
    vectorizer = idx["vectorizer"]
    tfidf = idx["tfidf"]
    doc_ids = idx["doc_ids"]
    qv = vectorizer.transform([query])
    sims = cosine_similarity(qv, tfidf).flatten()
    import numpy as np
    top_n = sims.argsort()[::-1][:top_k]
    results = []
    for i in top_n:
        score = float(sims[i])
        if score <= 0.0:
            continue
        did = doc_ids[i]
        # fetch doc content
        conn = _conn()
        cur = conn.cursor()
        cur.execute("SELECT id, title, content FROM documents WHERE id=?", (did,))
        row = cur.fetchone()
        conn.close()
        if row:
            results.append({"id": row[0], "title": row[1], "content": row[2], "score": score})
    return results
