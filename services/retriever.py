# services/retriever.py
import sqlite3
import os
from typing import List, Dict

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "bot.db")

def _conn():
    return sqlite3.connect(DB_PATH)

def init_retriever_tables():
    conn = _conn()
    cur = conn.cursor()
    # documents table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS documents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        content TEXT,
        created_at TEXT
    );
    """)
    # FTS virtual table (if sqlite supports FTS5)
    cur.execute("""CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(title, content, content='documents', content_rowid='id');""")
    conn.commit()
    conn.close()

def add_document(title: str, content: str, created_at: str):
    conn = _conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO documents (title, content, created_at) VALUES (?, ?, ?)", (title, content, created_at))
    rowid = cur.lastrowid
    # insert into FTS
    cur.execute("INSERT INTO documents_fts(rowid, title, content) VALUES (?, ?, ?)", (rowid, title, content))
    conn.commit()
    conn.close()

def search(query: str, limit: int = 5) -> List[Dict]:
    conn = _conn()
    cur = conn.cursor()
    # simple BM25-like using MATCH (FTS5)
    q = f"SELECT d.id, d.title, d.content FROM documents_fts f JOIN documents d ON f.rowid=d.id WHERE documents_fts MATCH ? LIMIT ?"
    cur.execute(q, (query, limit))
    rows = cur.fetchall()
    conn.close()
    return [{"id": r[0], "title": r[1], "content": r[2]} for r in rows]
