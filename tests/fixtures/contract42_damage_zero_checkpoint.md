# Contract 42 Damage-to-zero checkpoint

`contract42_damage_zero_checkpoint.json.gz` is a deterministic, exact-build Core
checkpoint for `test_contract42_damage_zero.py`. It was generated with installed Core
revision `6e86f44b87c4559a9297596d5d18dc4247b8cbc3` and build ID
`warhammer40k-core-v2:runtime-tree-sha256-v1:03db16dacfdb6152c4f6b841cab170561348f4ee29d60b581ce3215c6ab15765`.

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
`726bc609895cceae914c18069838ecd4b79b018c97a3cd97435accdc57d07ebf`;
the gzip SHA256 is
`b124fbe7d59fb9103f574cb41a87c9df81082dc52d46093b16d58a2af162a2cb`.
