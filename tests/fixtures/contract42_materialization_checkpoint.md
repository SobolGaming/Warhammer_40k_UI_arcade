# Contract 42 materialization checkpoint

`contract42_materialization_checkpoint.json.gz` is a deterministic, exact-build Core
checkpoint for the UI's real-session model-materialization regression. It was generated at
Core `6e86f44b87c4559a9297596d5d18dc4247b8cbc3` from
`tests/integration/test_horror_split_materialization.py`'s `_split_scenario` and
`_game_config`, followed by `tests/horror_destruction_helpers.py`'s
`resolve_horror_completion`. It contains a pending two-model Horror placement with source
destruction and roll events. It is test data, never a cross-version save.

Regenerate from the UI repository with:

```bash
uv run python scripts/generate_contract42_materialization_fixture.py
```

The generator checks the sibling Core checkout SHA. Its gzip output uses sorted compact JSON
and `mtime=0`. For the committed fixture, the uncompressed SHA256 is
`98b4dfe36babfe8bf5c01323656c8ff39bcac0cc864a668ed9ac6b90562e45ff`; the gzip
SHA256 is `93123130cced05ddfd5dc6179e6445e8b626d77b813796415fa9ec88bed2bbdf`.

The Core helper builds an in-progress domain scenario rather than a roster-start game. Its
checkpoint stores `config: null` so Core's exact-build restore authenticates the pending
state without rerunning roster mustering for the helper's ad hoc config. The test reads the
separately serialized config and recreates the same runtime bundle and phase handlers as the
source Core test before using `LocalGameSession` and `LocalSessionClient` for public view,
submission, and event checks. No Core test helper is imported by the regression at runtime.
