# base.py
from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document

class Retriever(ABC):  
    """Abstract base class for retrievers."""
    
    @abstractmethod
    def retrieve(self, query: str, k: int = 10) -> List[Document]:
        """Retrieves documents relevant to the query."""
        pass
    
    @abstractmethod
    def batch_retrieve(self, queries: List[str], k: int = 10) -> List[List[Document]]:
        """Retrieves documents for multiple queries."""
        pass