# Current Core 44.1 Damage-to-zero checkpoint

`contract42_damage_zero_checkpoint.json.gz` is a deterministic, exact-build Core
checkpoint for `test_contract42_damage_zero.py`. It was generated with installed Core
revision `fc12fa214642f1b1f2a31b56be7323b7d76dbebc` and build ID
`warhammer40k-core-v2:runtime-tree-sha256-v1:7e6f1a71a4ae347f98fa512cbcee8f8c9c03b409cf65c8464b55831daa6c6d54`.

The explicit generator imports pinned Core's
`tests/order93_save_damage_helpers.py`. It calls
`save_damage_session(damage_zero_replacement=True)` and then
`reach_save_damage_request(session, kind="damage_characteristic",
stage="failed-save-damage-replacement")`. Core's helper builds a compact,
in-progress shooting domain scenario with source effects and advances it through
Core decisions. This is **not** a roster-start traversal. The UI generator only
serializes the helper's resulting lifecycle; it does not seed lifecycle internals.
The committed checkpoint has 12 prior decision records and pending
`decision-request-000013`, a source-backed Channeller Stones
`000002532:4` SET 0 Damage operation. The regression imports no Core test helper;
it restores the lifecycle and exercises public `LocalGameSession` and
`LocalSessionClient` view, submission, event, and rejection behavior. This data
is tied to the exact engine build and is not a cross-version save.

Regenerate explicitly from the UI repository with:

```bash
UV_CACHE_DIR=/tmp/phase35-uv-cache uv run python scripts/generate_contract42_damage_zero_fixture.py
```

The generator verifies the installed Core revision and build identity and the
sibling checkout SHA. It writes sorted compact JSON in gzip with `mtime=0`.
For the committed fixture, the uncompressed SHA256 is
`53f5f65a98c3d36fd8e9ace2b1698c9d9a8cee2d3d08a51fae79eb2b6b3cf8b4`;
the gzip SHA256 is
`7b4156c4943817c9635fb911ded547e661e28b099c4296107faf427994b66d3b`.
