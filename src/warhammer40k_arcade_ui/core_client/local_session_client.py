"""Local in-process implementation of the public UI core-client facade."""

from __future__ import annotations

from dataclasses import dataclass, field

from warhammer40k_core.adapters.access_control import ViewerContext
from warhammer40k_core.adapters.contracts import AdapterGameSession
from warhammer40k_core.adapters.event_stream import EventStreamCursor
from warhammer40k_core.adapters.local_session import LocalGameSession
from warhammer40k_core.adapters.redaction import public_support_profile_payload
from warhammer40k_core.engine.decision_request import DecisionError
from warhammer40k_core.engine.game_state import GameConfig
from warhammer40k_core.engine.phase import GameLifecycleError, LifecycleStatus

from warhammer40k_arcade_ui.core_client.compatibility import require_supported_core_contract
from warhammer40k_arcade_ui.core_client.protocol import (
    JsonValue,
    UiClientProtocolError,
    UiClientStatus,
    UiClientSubmissionError,
    UiDecision,
    UiEventDelta,
    UiGameView,
    UiRulesCatalogView,
    UiSupportProfile,
    invalid_diagnostics_from_status,
    validate_json_value,
)


def _new_local_session() -> AdapterGameSession:
    return LocalGameSession()


def _new_rules_catalog_cache() -> dict[tuple[str, str], UiRulesCatalogView]:
    return {}


@dataclass(slots=True)
class LocalSessionClient:
    """UI-facing facade over only the core's public `AdapterGameSession` methods."""

    session: AdapterGameSession = field(default_factory=_new_local_session)
    _last_viewer_player_id: str | None = field(default=None, init=False, repr=False)
    _rules_catalog_cache: dict[tuple[str, str], UiRulesCatalogView] = field(
        default_factory=_new_rules_catalog_cache,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        require_supported_core_contract()

    def start_game(self, config: object) -> UiClientStatus:
        """Start a local game session through the public adapter facade."""

        if type(config) is not GameConfig:
            raise UiClientProtocolError("LocalSessionClient start_game requires a GameConfig.")
        self._last_viewer_player_id = None
        self._rules_catalog_cache.clear()
        return self._status_from_lifecycle(self.session.start(config))

    def advance_until_decision_or_terminal(self) -> UiClientStatus:
        """Advance until the core exposes an adapter-visible boundary."""

        return self._status_from_lifecycle(self.session.advance_until_decision_or_terminal())

    def get_view(self, viewer_player_id: str) -> UiGameView:
        """Return the strict viewer-scoped game projection."""

        view = UiGameView.from_payload(self.session.view(viewer_player_id=viewer_player_id))
        self._last_viewer_player_id = viewer_player_id
        return view

    def get_rules_catalog(self) -> UiRulesCatalogView:
        """Return the source-hashed catalog display projection."""

        catalog = UiRulesCatalogView.from_payload(self.session.rules_catalog_view())
        cache_key = (catalog.catalog_id, catalog.source_hash)
        cached = self._rules_catalog_cache.get(cache_key)
        if cached is not None:
            return cached
        self._rules_catalog_cache[cache_key] = catalog
        return catalog

    def get_support_profile(self, viewer_player_id: str) -> UiSupportProfile:
        """Return support evidence redacted for one player viewer."""

        public_payload = public_support_profile_payload(
            self.session.support_profile(),
            viewer=ViewerContext.for_player(viewer_player_id),
        )
        return UiSupportProfile.from_payload(public_payload)

    def get_events_since(self, cursor: int, viewer_player_id: str) -> UiEventDelta:
        """Return viewer-scoped event records after the supplied local cursor."""

        return UiEventDelta.from_payload(
            self.session.events_since(
                EventStreamCursor(value=cursor),
                viewer_player_id=viewer_player_id,
            )
        )

    def submit_finite(
        self,
        *,
        request_id: str,
        selected_option_id: str,
        result_id: str,
    ) -> UiClientStatus:
        """Submit one current engine-provided finite option."""

        try:
            status = self.session.submit_option(
                request_id=request_id,
                option_id=selected_option_id,
                result_id=result_id,
            )
        except (DecisionError, GameLifecycleError) as exc:
            raise UiClientSubmissionError(str(exc)) from exc
        return self._status_from_lifecycle(status)

    def submit_movement_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str,
    ) -> UiClientStatus:
        """Submit movement through the same public parameterized facade."""

        return self.submit_parameterized_payload(
            request_id=request_id,
            payload=payload,
            result_id=result_id,
        )

    def submit_parameterized_payload(
        self,
        *,
        request_id: str,
        payload: JsonValue,
        result_id: str,
    ) -> UiClientStatus:
        """Submit a JSON-safe parameterized proposal through the public facade."""

        try:
            status = self.session.submit_parameterized_payload(
                request_id=request_id,
                payload=validate_json_value(payload),
                result_id=result_id,
            )
        except (DecisionError, GameLifecycleError) as exc:
            raise UiClientSubmissionError(str(exc)) from exc
        return self._status_from_lifecycle(status)

    def _status_from_lifecycle(self, status: LifecycleStatus) -> UiClientStatus:
        decision, viewer_player_id = self._projected_decision_for_status(status)
        if viewer_player_id is not None:
            self._last_viewer_player_id = viewer_player_id
        message = status.message
        payload = validate_json_value(status.payload)
        status_kind = status.status_kind.value
        return UiClientStatus(
            stage=status.stage.value,
            status_kind=status_kind,
            decision=decision,
            message=message,
            payload=payload,
            invalid_diagnostics=invalid_diagnostics_from_status(
                status_kind=status_kind,
                message=message,
                payload=payload,
            ),
        )

    def _projected_decision_for_status(
        self,
        status: LifecycleStatus,
    ) -> tuple[UiDecision | None, str | None]:
        request = status.decision_request
        actor_id = None if request is None else request.actor_id
        viewer_player_id = actor_id or self._last_viewer_player_id
        if viewer_player_id is None:
            return None, None
        view = UiGameView.from_payload(self.session.view(viewer_player_id=viewer_player_id))
        return view.pending_decision, viewer_player_id
