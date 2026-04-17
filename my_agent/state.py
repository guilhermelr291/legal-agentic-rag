from langchain_core.messages import AnyMessage
from typing import TypedDict, Annotated
import operator
from typing import List


class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    documents: List[str]
    generation: str
    queries_for_retrieval: List[str]
