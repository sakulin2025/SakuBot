"""Stable script envelope. TypedDict values remain ordinary dictionaries."""
from typing import Annotated, Generic, TypeVar, TypedDict

DataT = TypeVar('DataT')
ParamsT = TypeVar('ParamsT')


class Event(TypedDict, Generic[DataT]):
    id: Annotated[str, 'Producer event deduplication ID']
    source: Annotated[str, 'Actual full source ID without wildcard']
    at: Annotated[float, 'Framework dispatch time, Unix seconds, UTC epoch']
    data: DataT
