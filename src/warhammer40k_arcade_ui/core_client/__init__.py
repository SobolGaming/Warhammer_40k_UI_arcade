"""UI-facing core client facade."""

from warhammer40k_arcade_ui.core_client.fake_client import (
    FakeCoreClient,
    SubmittedFiniteDecision,
    SubmittedMovementPayload,
)
from warhammer40k_arcade_ui.core_client.local_session_client import LocalSessionClient
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonObject,
    JsonValue,
    UiClientProtocolError,
    UiClientStatus,
    UiCoreClient,
    UiDecision,
    UiEventDelta,
    UiFiniteOption,
    UiGameView,
    UiInvalidDiagnostic,
    UiMovementProposalRequest,
)

__all__ = [
    "FakeCoreClient",
    "JsonObject",
    "JsonValue",
    "LocalSessionClient",
    "SubmittedFiniteDecision",
    "SubmittedMovementPayload",
    "UiClientProtocolError",
    "UiClientStatus",
    "UiCoreClient",
    "UiDecision",
    "UiEventDelta",
    "UiFiniteOption",
    "UiGameView",
    "UiInvalidDiagnostic",
    "UiMovementProposalRequest",
]
