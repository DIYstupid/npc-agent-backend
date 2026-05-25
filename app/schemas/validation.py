from typing import Annotated

from pydantic import StringConstraints


RESOURCE_ID_PATTERN = r"^[A-Za-z0-9_.:-]+$"
RESOURCE_ID_MAX_LENGTH = 64
MEMORY_TYPE_MAX_LENGTH = 32
TAG_MAX_LENGTH = 32
CHAT_MESSAGE_MAX_LENGTH = 2000
MEMORY_TEXT_MAX_LENGTH = 4000
SEARCH_QUERY_MAX_LENGTH = 500

ResourceId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=RESOURCE_ID_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]
MemoryType = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MEMORY_TYPE_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]
Tag = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=TAG_MAX_LENGTH,
        pattern=RESOURCE_ID_PATTERN,
    ),
]
ChatText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=CHAT_MESSAGE_MAX_LENGTH,
    ),
]
MemoryText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=MEMORY_TEXT_MAX_LENGTH,
    ),
]
SearchQuery = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=SEARCH_QUERY_MAX_LENGTH,
    ),
]
