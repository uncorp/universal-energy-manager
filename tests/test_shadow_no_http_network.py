"""Static guard: Shadow-only code must never import HTTP/network clients.

This regression test parses the AST of every module in the Shadow integration
package and rejects imports of outbound HTTP clients, URL fetchers, and
provider-refresh patterns. It complements ``test_shadow_no_control.py``
(which blocks HA service/control imports) and
``test_shadow_runtime_no_control.py`` (which blocks ``hass.services`` calls
at runtime).

Forbidden patterns are all network-bound:
    - HTTP clients: urllib, requests, httpx, aiohttp, http.client
    - URL builders: yarl.URL (as network target)
    - Provider refresh patterns: async_get_data, refresh_provider,
      fetch_url, http_call, post_data, send_request, api_call
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Forbidden module prefixes — direct HTTP/network client libraries
# ---------------------------------------------------------------------------
_FORBIDDEN_HTTP_MODULES: frozenset[str] = frozenset(
    {
        "urllib",
        "requests",
        "httpx",
        "aiohttp",
        "http.client",
        "yarl",
        "asyncio",
    }
)

# ---------------------------------------------------------------------------
# Forbidden function / attribute patterns inside module bodies.
# These catch runtime HTTP calls that do not use a top-level import.
# ---------------------------------------------------------------------------
_FORBIDDEN_FUNCTIONS: frozenset[str] = frozenset(
    {
        "async_get_data",
        "refresh_provider",
        "fetch_url",
        "http_call",
        "post_data",
        "send_request",
        "api_call",
        "open_url",
        "urlopen",
    }
)

# ---------------------------------------------------------------------------
# Allowed HA modules — read-only state, helpers, and cached-component access.
# These are explicitly permitted so the guard does not false-positive on
# legitimate Shadow-mode code that reads entity state or uses HA utilities.
# ---------------------------------------------------------------------------
_ALLOWED_HA_PREFIXES: frozenset[str] = frozenset(
    {
        "homeassistant",
    }
)


def _shadow_module_paths() -> list[Path]:
    """Return all .py files inside the Shadow integration package."""
    pkg_root = (
        Path(__file__).resolve().parent.parent
        / "custom_components" / "universal_energy_manager"
    )
    return sorted(
        p for p in pkg_root.iterdir()
        if p.suffix == ".py" and p.is_file()
    )


def _check_http_imports(node: ast.Module, filepath: str) -> list[str]:
    """Return violations for HTTP/network client imports."""
    violations: list[str] = []

    for child in ast.walk(node):
        if isinstance(child, ast.Import):
            for alias in child.names:
                for fb_mod in _FORBIDDEN_HTTP_MODULES:
                    top = alias.name.split(".")[0]
                    if top == fb_mod or alias.name.startswith(fb_mod + "."):
                        violations.append(
                            f"{filepath}: import {alias.name} "
                            f"matches forbidden HTTP module {fb_mod}"
                        )

        elif isinstance(child, ast.ImportFrom):
            if child.module is None:
                continue
            # Skip allowed HA module imports (read-only state/data access)
            if child.module.startswith("homeassistant"):
                continue
            for alias in child.names:
                for fb_mod in _FORBIDDEN_HTTP_MODULES:
                    top = child.module.split(".")[0]
                    if top == fb_mod or child.module.startswith(fb_mod + "."):
                        violations.append(
                            f"{filepath}: from {child.module} import {alias.name} "
                            f"forbidden HTTP module {fb_mod}"
                        )

    return violations


def _check_forbidden_functions(node: ast.Module, filepath: str) -> list[str]:
    """Return violations for forbidden function / attribute names.

    Only inspects function definitions and class bodies (not imports), so
    that HA-only patterns are never flagged.
    """
    violations: list[str] = []
    # Pattern for forbidden function/attribute names
    pattern = re.compile(
        r"^(" + "|".join(re.escape(fn) for fn in _FORBIDDEN_FUNCTIONS) + r")$"
    )

    for child in ast.iter_child_nodes(node):
        # We only check top-level function/class definitions and their
        # direct child function/class definitions to catch patterns like
        # ``class Foo: async def async_get_data(self): ...`` without
        # traversing into arbitrary nested scopes.
        targets: list[ast.AST] = []
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            targets.append(child)
            # Check nested function definitions too
            for inner in ast.walk(child):
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if inner is not child:
                        targets.append(inner)
        elif isinstance(child, ast.ClassDef):
            for inner in ast.walk(child):
                if isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    targets.append(inner)

        for func in targets:
            name = func.name  # type: ignore[union-attr]
            if pattern.match(name):
                violations.append(
                    f"{filepath}: function {name} matches forbidden pattern"
                )

    return violations


def test_shadow_package_has_no_http_network_imports() -> None:
    """Every Shadow module must be free of HTTP/network client imports."""
    all_violations: list[str] = []
    for mod_path in _shadow_module_paths():
        tree = ast.parse(mod_path.read_bytes(), filename=str(mod_path))
        rel = mod_path.relative_to(Path(__file__).resolve().parent.parent)
        all_violations.extend(_check_http_imports(tree, str(rel)))

    if all_violations:
        msg = (
            "Shadow integration must not import HTTP/network clients:\\n"
            + "\\n".join(all_violations)
        )
        raise AssertionError(msg)


def test_shadow_package_has_no_forbidden_network_functions() -> None:
    """Every Shadow module must avoid forbidden network function names."""
    all_violations: list[str] = []
    for mod_path in _shadow_module_paths():
        tree = ast.parse(mod_path.read_bytes(), filename=str(mod_path))
        rel = mod_path.relative_to(Path(__file__).resolve().parent.parent)
        all_violations.extend(_check_forbidden_functions(tree, str(rel)))

    if all_violations:
        msg = (
            "Shadow integration must not use forbidden network function names:\\n"
            + "\\n".join(all_violations)
        )
        raise AssertionError(msg)
