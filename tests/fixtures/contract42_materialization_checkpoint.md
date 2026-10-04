# Current Core 44.1 materialization checkpoint

`contract42_materialization_checkpoint.json.gz` is a deterministic, exact-build Core
checkpoint for the UI's real-session model-materialization regression. It was generated at
Core `fc12fa214642f1b1f2a31b56be7323b7d76dbebc` / build ID
`warhammer40k-core-v2:runtime-tree-sha256-v1:7e6f1a71a4ae347f98fa512cbcee8f8c9c03b409cf65c8464b55831daa6c6d54` from
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
`9cde26c843832883b4636bf1fdf4d24d4aa8df2751e15aaacff34380138ac0cc`; the gzip
SHA256 is `5b13a5b88fbcc1dfb7808e4478f0f29c930c27ba279dd57a54a7bbc9b7b525e6`.

The Core helper builds an in-progress domain scenario rather than a roster-start game. Its
checkpoint stores `config: null` so Core's exact-build restore authenticates the pending
state without rerunning roster mustering for the helper's ad hoc config. The test reads the
separately serialized config and recreates the same runtime bundle and phase handlers as the
source Core test before using `LocalGameSession` and `LocalSessionClient` for public view,
submission, and event checks. No Core test helper is imported by the regression at runtime.
