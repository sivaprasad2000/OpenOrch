import enum
from dataclasses import dataclass, field


class LLMProvider(str, enum.Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    META = "meta"
    GOOGLE = "google"
    MISTRAL = "mistral"
    COHERE = "cohere"
    OPEN_ROUTER = "open_router"


@dataclass
class Message:
    """A single turn in a conversation."""

    role: str  # "user" | "assistant"
    content: str


@dataclass
class LLMResponse:
    """Normalised response returned by every provider client."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    raw: dict = field(default_factory=dict, repr=False)
