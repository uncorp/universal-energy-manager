"""Static guard: the Shadow-only package must never import HA control/service APIs.

This regression test parses the AST of every module in the Shadow integration
package and rejects imports of Home Assistant service-call or control-command
entry-points. It exercises its own failure path via the ``_FORBIDDEN`` list so
that any future developer (or model) adding a service call will get a clear,
deterministic failure.

Forbidden patterns (all are HA service/control entry points):
    - call_service, async_call_service, call_from_service, fire_mqtt_service,
      async_fire_mqtt_service
    - homeassistant.core.ServiceCall, homeassistant.core.ServiceResponse,
      homeassistant.core.ServiceRegistry
"""

from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------
# Forbidden imports: module path prefix + allowed names
# ---------------------------------------------------------------------------
_FORBIDDEN_CALLABLES: frozenset[str] = frozenset(
    {
        "call_service",
        "async_call_service",
        "call_from_service",
        "fire_mqtt_service",
        "async_fire_mqtt_service",
    }
)

_FORBIDDEN_MODULES: frozenset[str] = frozenset(
    {
        "homeassistant.core.ServiceCall",
        "homeassistant.core.ServiceResponse",
        "homeassistant.core.ServiceRegistry",
        "homeassistant.components.mqtt",
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
        if p.suffix == ".py" and p.name != "__pycache__"
    )


def _parse_source(path: Path) -> ast.Module:
    return ast.parse(path.read_bytes(), filename=str(path))


def _check_imports(node: ast.Module, filepath: str) -> list[str]:
    """Return a list of violations found in this module."""
    violations: list[str] = []

    for child in ast.walk(node):
        # --- import statements: ``import X.Y.Z`` or ``from X import Y`` ---
        if isinstance(child, ast.Import):
            for alias in child.names:
                full_name = alias.name
                # Check against forbidden module prefixes
                for fb_mod in _FORBIDDEN_MODULES:
                    if full_name == fb_mod or full_name.startswith(fb_mod + "."):
                        violations.append(
                            f"{filepath}: import {full_name} "
                            f"matches forbidden module pattern {fb_mod}"
                        )
                # Check for imports that re-export a forbidden callable
                if alias.asname:
                    if alias.asname in _FORBIDDEN_CALLABLES:
                        violations.append(
                            f"{filepath}: aliased import of forbidden name {alias.asname}"
                        )

        elif isinstance(child, ast.ImportFrom):
            if child.module is None:
                continue
            full_prefix = child.module
            for alias in child.names:
                # Direct forbidden name import: from X import call_service
                if alias.name in _FORBIDDEN_CALLABLES:
                    violations.append(
                        f"{filepath}: from {full_prefix} import {alias.name} "
                        f"(forbidden callable)"
                    )
                # Forbidden module import: from homeassistant.core import ServiceCall
                full_import = f"{full_prefix}.{alias.name}"
                for fb_mod in _FORBIDDEN_MODULES:
                    if full_import == fb_mod or full_import.startswith(fb_mod + "."):
                        violations.append(
                            f"{filepath}: from {full_prefix} import {alias.name} "
                            f"(forbidden module {fb_mod})"
                        )

    return violations


def test_shadow_package_has_no_service_control_imports() -> None:
    """Every Shadow module must be free of HA service-call / control-command imports."""
    all_violations: list[str] = []
    for mod_path in _shadow_module_paths():
        tree = _parse_source(mod_path)
        rel = mod_path.relative_to(Path(__file__).resolve().parent.parent)
        all_violations.extend(_check_imports(tree, str(rel)))

    if all_violations:
        msg = (
            "Shadow integration must not import HA service/control APIs:\n"
            + "\n".join(all_violations)
        )
        raise AssertionError(msg)
