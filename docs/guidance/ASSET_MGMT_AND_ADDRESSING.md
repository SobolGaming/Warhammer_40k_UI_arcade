The clean pattern is:

**Package resources are immutable defaults. User config and user assets are filesystem files. Cache is only for disposable/extracted/generated things.**

For your repo specifically, I would **not** make `~/.cache/warhammer-40k-ui` the user-visible home for editable config. Use `platformdirs.user_config_path()` for YAML preferences/HUD config and `platformdirs.user_data_path()` for durable imported art/assets. Keep `user_cache_path()` for generated thumbnails, extracted temporary resources, compiled atlases, etc. `platformdirs` explicitly exposes separate user config, data, cache, state, log, and runtime paths, and it handles Linux/macOS/Windows conventions for you. ([platformdirs][1])

## Recommended model

Use a three-layer source model:

```text
1. built-in package defaults
   src/warhammer40k_arcade_ui/resources/preferences/default.yaml
   src/warhammer40k_arcade_ui/resources/hud/default-hud.yaml
   src/warhammer40k_arcade_ui/resources/art/...

2. platform user overrides
   platformdirs.user_config_path("warhammer40k-arcade-ui") / "ui-preferences.yaml"
   platformdirs.user_config_path("warhammer40k-arcade-ui") / "hud/default-hud.yaml"

3. explicit runtime overrides
   warhammer40k-arcade-ui --ui-prefs path/to/profile.yaml
   warhammer40k-arcade-ui --hud-profile path/to/hud.yaml
   warhammer40k-arcade-ui --asset-dir path/to/assets
```

The important bit is that **the default install remains pristine**. When the user wants customization, you export/copy a starter file into their config directory or to a chosen shareable folder.

Your current repo is already close: the project depends on `platformdirs`, exposes `warhammer40k-export-preferences`, and already accepts `--ui-prefs PATH`. ([GitHub][2]) The main thing I would change is that runtime YAML defaults should move out of top-level `docs/` and into the import package, because your current Hatch wheel config selects `src/warhammer40k_arcade_ui` as the package tree, while the README currently points runtime HUD/preferences examples at `docs/...`. ([GitHub][2])

## Do not make users type `:pkg_name:path`

Your old `:pkg_name:filepath_in_pkg` idea is mechanically reasonable, but I would not expose that as the normal player-facing interface. It leaks Python packaging internals and gets awkward fast.

Instead:

```text
--ui-prefs ~/Downloads/kyle-preferences.yaml       # normal file
--profile default                                  # named built-in profile
--profile dense-debug                              # named built-in profile
--profile command-bench                            # named built-in profile
```

Inside code, you can still represent sources explicitly:

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

@dataclass(frozen=True, slots=True)
class ConfigSource:
    kind: Literal["builtin", "user_default", "explicit_path"]
    name: str
    path: Path | None = None
```

That gives you the same power as `:pkg_name:path`, but without making users know about Python packages.

For YAML fields that need to reference other files, I would use this rule:

```text
composition_profile: default-hud          # known built-in ID
composition_profile: hud/my-custom.yaml   # relative to this YAML file
composition_profile: /abs/path/hud.yaml   # explicit absolute path
```

So the user can share a folder like:

```text
my-warhammer-ui-profile/
  ui-preferences.yaml
  hud/
    my-custom-hud.yaml
  assets/
    objective-marker.png
    faction-icons/
```

Then relative references inside `ui-preferences.yaml` resolve relative to that file’s directory. This is much more pleasant than package-path notation and makes sharing obvious.

## Where each file should live

Use this split:

```text
user_config_path()
  ui-preferences.yaml
  hud/*.yaml
  profiles/*.yaml

user_data_path()
  assets/
  themes/
  imported-art/
  downloaded-content/
  mods/

user_cache_path()
  generated-atlases/
  extracted-package-assets/
  thumbnails/
  render-cache/

user_state_path()
  event-traces/
  crash-bundles/
  recent-files.json
```

That also matches what your README is already doing conceptually for state-like diagnostics: event traces and crash bundles are documented under `~/.local/state/warhammer40k-arcade-ui/...`. ([GitHub][3])

## Package resource loading

For built-in files, use `importlib.resources.files()`. Python’s docs emphasize that package resources are not guaranteed to exist as normal files/directories on disk; they may come from zip imports or other import loaders. ([Python documentation][4])

```python
from importlib.resources import files
from pathlib import PurePosixPath

RESOURCE_PACKAGE = "warhammer40k_arcade_ui.resources"

def read_builtin_text(relative_resource: str) -> str:
    rel = PurePosixPath(relative_resource)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe resource path: {relative_resource!r}")

    return (
        files(RESOURCE_PACKAGE)
        .joinpath(*rel.parts)
        .read_text(encoding="utf-8")
    )
```

For APIs that require an actual filesystem path, use `as_file()`. The Python docs call this out as the right tool when the `Traversable` read APIs are insufficient and a real file or directory path is required; the temporary extraction is cleaned up when the context exits. ([Python documentation][4])

```python
from contextlib import contextmanager
from importlib.resources import as_file, files
from pathlib import Path, PurePosixPath
from typing import Iterator

RESOURCE_PACKAGE = "warhammer40k_arcade_ui.resources"

@contextmanager
def builtin_resource_path(relative_resource: str) -> Iterator[Path]:
    rel = PurePosixPath(relative_resource)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe resource path: {relative_resource!r}")

    traversable = files(RESOURCE_PACKAGE).joinpath(*rel.parts)
    with as_file(traversable) as real_path:
        yield real_path
```

For game assets, be careful with lifetime. If Arcade or another graphics API reads the file immediately, a short `with as_file(...)` block is fine. If an API stores the path and reloads lazily later, keep the `as_file()` context alive for the lifetime of the app, or copy the resource into `user_cache_path()` / an app-managed cache.

## Config loader shape

This is the pattern I would use for UI prefs and HUD configs:

```python
from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path, PurePosixPath
from typing import Any, Literal

import yaml
from platformdirs import user_config_path, user_data_path, user_cache_path

APPNAME = "warhammer40k-arcade-ui"
RESOURCE_PACKAGE = "warhammer40k_arcade_ui.resources"


@dataclass(frozen=True, slots=True)
class LoadedConfig:
    payload: dict[str, Any]
    source_kind: Literal["builtin", "user_default", "explicit_path"]
    display_name: str
    path: Path | None


def config_dir(*, ensure_exists: bool = False) -> Path:
    return user_config_path(APPNAME, appauthor=False, ensure_exists=ensure_exists)


def data_dir(*, ensure_exists: bool = False) -> Path:
    return user_data_path(APPNAME, appauthor=False, ensure_exists=ensure_exists)


def cache_dir(*, ensure_exists: bool = False) -> Path:
    return user_cache_path(APPNAME, appauthor=False, ensure_exists=ensure_exists)


def _read_builtin_yaml(relative_resource: str) -> dict[str, Any]:
    rel = PurePosixPath(relative_resource)
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"unsafe resource path: {relative_resource!r}")

    text = (
        files(RESOURCE_PACKAGE)
        .joinpath(*rel.parts)
        .read_text(encoding="utf-8")
    )
    loaded = yaml.safe_load(text)
    return loaded or {}


def _read_yaml_file(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded or {}


def load_ui_preferences(explicit_path: Path | None = None) -> LoadedConfig:
    if explicit_path is not None:
        return LoadedConfig(
            payload=_read_yaml_file(explicit_path),
            source_kind="explicit_path",
            display_name=str(explicit_path),
            path=explicit_path,
        )

    user_path = config_dir() / "ui-preferences.yaml"
    if user_path.exists():
        return LoadedConfig(
            payload=_read_yaml_file(user_path),
            source_kind="user_default",
            display_name=str(user_path),
            path=user_path,
        )

    return LoadedConfig(
        payload=_read_builtin_yaml("preferences/default.yaml"),
        source_kind="builtin",
        display_name="builtin:preferences/default.yaml",
        path=None,
    )
```

That gives you this behavior:

```text
No config file exists:
  use packaged default

User has ~/.config/.../ui-preferences.yaml:
  use that

User passes --ui-prefs ./friend-profile.yaml:
  use that exact file
```

## Export/init command

Do not silently expand everything into cache on first launch. Instead, provide a very obvious command:

```text
warhammer40k-config paths
warhammer40k-config init
warhammer40k-config init --overwrite
warhammer40k-export-preferences --profile default --output <path>
```

Your existing `warhammer40k-export-preferences` command is a good seed for this. The README already tells users to generate starter preference profiles with that command and load profiles with `--ui-prefs path/to/profile.yaml`. ([GitHub][3])

Implementation sketch:

```python
import shutil
from pathlib import Path
from importlib.resources import files, as_file

from platformdirs import user_config_path

APPNAME = "warhammer40k-arcade-ui"
RESOURCE_PACKAGE = "warhammer40k_arcade_ui.resources"


def install_default_configs(*, overwrite: bool = False) -> list[Path]:
    dst_root = user_config_path(APPNAME, appauthor=False, ensure_exists=True)

    copies = [
        ("preferences/default.yaml", dst_root / "ui-preferences.yaml"),
        ("hud/default-hud.yaml", dst_root / "hud" / "default-hud.yaml"),
        ("hud/command-bench-hud.yaml", dst_root / "hud" / "command-bench-hud.yaml"),
    ]

    written: list[Path] = []
    for src_rel, dst in copies:
        if dst.exists() and not overwrite:
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        src = files(RESOURCE_PACKAGE).joinpath(*src_rel.split("/"))
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        written.append(dst)

    return written
```

For art directories:

```python
from importlib.resources import as_file, files
from platformdirs import user_data_path

def install_default_art_pack(*, overwrite: bool = False) -> Path:
    dst_root = (
        user_data_path("warhammer40k-arcade-ui", appauthor=False, ensure_exists=True)
        / "assets"
        / "default"
    )

    if dst_root.exists() and not overwrite:
        return dst_root

    src = files("warhammer40k_arcade_ui.resources").joinpath("art")
    with as_file(src) as src_path:
        if dst_root.exists():
            shutil.rmtree(dst_root)
        shutil.copytree(src_path, dst_root)

    return dst_root
```

I would only copy art like this if the user is explicitly installing/exporting a theme or if a library truly needs persistent physical files. Otherwise, read packaged art directly with `importlib.resources`.

## Packaging layout

I would move runtime resources into the package:

```text
src/
  warhammer40k_arcade_ui/
    resources/
      __init__.py
      preferences/
        default.yaml
        dense-debug.yaml
        keyboard-heavy.yaml
        command-bench.yaml
      hud/
        default-hud.yaml
        command-bench-hud.yaml
      art/
        ...
```

Because you are using Hatchling and already have:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/warhammer40k_arcade_ui"]
```

placing resources under `src/warhammer40k_arcade_ui` keeps them inside the selected package tree. Hatch’s `packages` option selects the package directory and rewrites the `src` prefix away in the wheel. ([GitHub][2])

If you strongly prefer to keep runtime resources outside the package tree, use Hatch’s `force-include` to map them into the installed package. Hatch documents `force-include` for including files/directories from elsewhere and mapping them to a desired distribution path. ([Hatch][5])

Example:

```toml
[tool.hatch.build.targets.wheel.force-include]
"docs/preferences" = "warhammer40k_arcade_ui/resources/preferences"
"docs/hud" = "warhammer40k_arcade_ui/resources/hud"
"art" = "warhammer40k_arcade_ui/resources/art"
```

But I would prefer moving runtime defaults under `src/.../resources` and leaving `docs/` as documentation/examples only.

## How I would resolve HUD/art references

For a config file loaded from disk:

```yaml
profile_name: kyle-table
hud:
  composition_profile: hud/table-hud.yaml
assets:
  roots:
    - assets
```

Resolve relative paths against the config file’s directory:

```python
def resolve_reference(value: str, *, config_file: Path | None) -> ConfigSource:
    known_builtins = {
        "default-hud": "hud/default-hud.yaml",
        "command-bench-hud": "hud/command-bench-hud.yaml",
    }

    if value in known_builtins:
        return ConfigSource(kind="builtin", name=known_builtins[value])

    candidate = Path(value)
    if candidate.is_absolute():
        return ConfigSource(kind="explicit_path", name=value, path=candidate)

    if config_file is not None:
        return ConfigSource(
            kind="explicit_path",
            name=value,
            path=(config_file.parent / candidate).resolve(),
        )

    return ConfigSource(kind="builtin", name=value)
```

This gives the user a natural mental model: “files next to my profile are part of my profile.”

## When to use merging vs replacement

For now, I would use **whole-profile replacement**:

```text
default packaged profile OR user profile OR explicit profile
```

That is simpler, easier to debug, and very shareable.

Later, if you want small overlays, add an explicit inheritance mechanism:

```yaml
schema_version: 1
extends: default
profile_name: kyle-keyboard-heavy
hotkeys:
  - command_id: confirm
    key: enter
```

But do not silently deep-merge arbitrary files until the schema is stable. Deep merges can become confusing when lists are involved, especially hotkeys, HUD zones, widget declarations, and art packs.

## My concrete recommendation

For `Warhammer_40k_UI_arcade`, I would implement this path:

1. Move runtime defaults from `docs/preferences` and `docs/hud` into `src/warhammer40k_arcade_ui/resources/...`.
2. Keep `docs/` examples, but make them documentation copies, not runtime dependencies.
3. Keep `--ui-prefs PATH` for explicit file overrides.
4. Add named built-in profile selection separately, such as `--profile default`, `--profile dense-debug`, `--profile command-bench`.
5. Add `warhammer40k-config paths` and `warhammer40k-config init` so users can discover and initialize their writable config directory.
6. Use `user_config_path()` for mutable YAML, `user_data_path()` for durable user art/themes/mods, and `user_cache_path()` only for rebuildable generated/extracted files.
7. Avoid user-facing `:pkg_name:path`; use internal `ConfigSource`/`ResourceSource` types and user-facing names/paths instead.

That gives you installable package defaults, user-editable overrides, shareable profile folders, and future asset-pack support without tying the user interface to Python packaging internals.

[1]: https://platformdirs.readthedocs.io/en/latest/api.html "API - platformdirs"
[2]: https://github.com/SobolGaming/Warhammer_40k_UI_arcade/blob/main/pyproject.toml "Warhammer_40k_UI_arcade/pyproject.toml at main · SobolGaming/Warhammer_40k_UI_arcade · GitHub"
[3]: https://github.com/SobolGaming/Warhammer_40k_UI_arcade "GitHub - SobolGaming/Warhammer_40k_UI_arcade · GitHub"
[4]: https://docs.python.org/3/library/importlib.resources.html "importlib.resources – Package resource reading, opening and access — Python 3.14.5 documentation"
[5]: https://hatch.pypa.io/1.16/config/build/ "Build configuration - Hatch"
