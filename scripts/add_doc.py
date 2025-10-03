# scripts/add_doc.py
from services.retriever_tfidf import add_document, rebuild_index
from datetime import datetime

def main():
    title = input("Title: ").strip()
    print("Enter content (end with EOF / Ctrl+Z then Enter on Windows):")
    import sys
    content = sys.stdin.read().strip()
    if not content:
        print("Нет контента — выходим.")
        return
    add_document(title, content, datetime.utcnow().isoformat())
    print("Документ добавлен. Пересобираю индекс...")
    rebuild_index()
    print("Готово.")

if __name__ == "__main__":
    main()
