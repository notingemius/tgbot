# add_knowledge.py
from services.retriever import add_document, init_retriever_tables
from datetime import datetime
init_retriever_tables()
add_document("Bank policy", "Your bank's policy on fees is ...", datetime.utcnow().isoformat())
print("Added")
