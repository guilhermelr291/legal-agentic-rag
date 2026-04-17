import asyncio
from typing import List
from concurrent.futures import ThreadPoolExecutor
from langchain_core.documents import Document
from langchain_core.retrievers import EnsembleRetriever as LangChainEnsembleRetriever
from my_agent.retrievers.base import Retriever


class EnsembleRetriever(Retriever):
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
        return self._ensemble.invoke(query, config={"k": k})

    def batch_retrieve(self, queries: List[str], k: int = 10) -> List[List[Document]]:
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

    async def abatch_retrieve(self, queries: List[str], k: int = 10) -> List[List[Document]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.batch_retrieve,
            queries,
            k
        )
