from langchain_core.messages import AnyMessage
from typing import TypedDict, Annotated
import operator


class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]