import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional
from langchain_core.documents import Document
from langchain_core.retrievers import EnsembleRetriever as LangChainEnsembleRetriever
from my_agent.retrievers.base import Retriever


logger = logging.getLogger(__name__)

DEFAULT_HYBRID_WEIGHTS: tuple[float, float] = (0.7, 0.3)


class EnsembleRetriever(Retriever):
    def __init__(
        self,
        retrievers: List,
        weights: Optional[List[float]] = None,
        c: float = 60,
        max_workers: int = 5,
    ):
        self.retrievers = retrievers
        if weights is None and len(retrievers) == 2:
            self.weights = list(DEFAULT_HYBRID_WEIGHTS)
        else:
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
        errors = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_query = {
                executor.submit(self.retrieve, query, k): query
                for query in queries
            }

            results = []
            for future in future_to_query:
                query = future_to_query[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"Retrieval error for query '{query}': {e}", exc_info=True)
                    errors.append({"query": query, "error": str(e)})
                    results.append([])

        if errors:
            logger.warning(f"Failed to retrieve for {len(errors)} out of {len(queries)} queries")

        return results

    async def abatch_retrieve(self, queries: List[str], k: int = 10) -> List[List[Document]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.batch_retrieve,
            queries,
            k
        )
