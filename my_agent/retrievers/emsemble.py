# ensemble.py
from typing import List
from concurrent.futures import ThreadPoolExecutor
from langchain_core.documents import Document
from langchain_core.retrievers import EnsembleRetriever as LangChainEnsembleRetriever
from my_agent.retrievers.base import Retriever  # Importa ABC


class EnsembleRetriever(Retriever):  # <-- Herda de ABC
    """
    Ensemble retriever implementation.
    Must implement all abstract methods or Python raises TypeError!
    """
    
    def __init__(
        self,
        retrievers: List,
        weights: List[float] = None,
        c: float = 60,
        max_workers: int = 4,
    ):
        self.retrievers = retrievers
        self.weights = weights
        self.c = c
        self.max_workers = max_workers
        
        # Converte para retrievers LangChain internamente
        langchain_retrievers = []
        for r in retrievers:
            if hasattr(r, 'as_retriever'):
                langchain_retrievers.append(r.as_retriever())
            else:
                langchain_retrievers.append(r)
        
        self._ensemble = LangChainEnsembleRetriever(
            retrievers=langchain_retrievers,
            weights=self.weights,
            c=self.c,
        )

    def retrieve(self, query: str, k: int = 10) -> List[Document]:
        """Required: implement abstract method."""
        return self._ensemble.invoke(query, config={"k": k})

    def batch_retrieve(self, queries: List[str], k: int = 10) -> List[List[Document]]:
        """Required: implement abstract method."""
        if len(queries) == 1:
            return [self.retrieve(queries[0], k)]

        workers = min(self.max_workers, len(queries))

        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(self.retrieve, query, k) for query in queries
            ]

            results = []
            for future in futures:
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"Retrieval error: {e}")
                    results.append([])

        return results