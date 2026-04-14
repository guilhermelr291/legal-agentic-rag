from typing import List
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

class FAISSVectorStore:
    def __init__(self, vector_store: FAISS):
        self.vector_store = vector_store
    
    def add_documents(self, documents: List[Document]):
        self.vector_store.add_documents(documents)
    
    def search(self, query: str, k: int = 10):
        return self.vector_store.similarity_search_with_score(query, k)
    
    def as_retriever(self):
        return self.vector_store.as_retriever()
    
    def save(self, path: str):
        self.vector_store.save_local(path)
    
    @classmethod
    def load(cls, path: str, embeddings):
        store = FAISS.load_local(path, embeddings)
        return cls(store)