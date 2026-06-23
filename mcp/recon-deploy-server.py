"""OpenRecon Deployment MCP (standalone server).

Gives a coding agent tools + context to install and configure OpenRecon from a filled
INTAKE.md: inspect/validate the intake, scaffold the stack config, bring the stack up,
run a reconcile, and verify health. Connect alongside the companion MCPs in mcp/README.md
(Postgres, Docker, filesystem, the target GL/DMS) to wire the business systems.

Run by PATH (not `python -m`, which would clash with the `mcp` SDK package name):
    pip install -r mcp/requirements.txt
    RECON_REPO=/path/to/repo python mcp/recon-deploy-server.py
The stack API base is RECON_API (default http://localhost:8002).
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from pathlib import Path

from mcp.server.fastmcp import FastMCP

REPO = Path(os.environ.get("RECON_REPO", Path(__file__).resolve().parents[1]))
STACK = REPO / "stack"
API = os.environ.get("RECON_API", "http://localhost:8002").rstrip("/")

mcp = FastMCP("recon-deploy", instructions=(
    "Install/configure OpenRecon from a filled INTAKE.md. Read the recon:// resources first, then: "
    "intake_status -> scaffold_config -> stack('up') -> reconcile -> verify_deploy. "
    "Implement any stub adapter named in the intake before reconciling. GL adapters are read-only."
))


def _read(rel: str) -> str:
    p = REPO / rel
    return p.read_text(encoding="utf-8") if p.exists() else f"[missing] {rel}"


def _sh(args: list[str], cwd: Path, timeout: int = 180) -> str:
    try:
        p = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout)
        return f"rc={p.returncode}\n{(p.stdout or '')}{('[stderr] ' + p.stderr) if p.stderr.strip() else ''}".strip()
    except Exception as e:  # noqa: BLE001
        return f"[error] {e}"


def _http(path: str, method: str = "GET", timeout: int = 30) -> str:
    try:
        req = urllib.request.Request(f"{API}{path}", method=method)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode()
    except Exception as e:  # noqa: BLE001
        return f"[error] {e}"


# ───────────── resources (context) ─────────────
@mcp.resource("recon://intake-template")
def r_intake() -> str:
    """The blank deployment intake the user fills out."""
    return _read("INTAKE.md")


@mcp.resource("recon://intake-example")
def r_intake_example() -> str:
    """A worked intake (Dynamics GP + Laserfiche) as a reference answer set."""
    return _read("INTAKE.example.md")


@mcp.resource("recon://deployment-guide")
def r_deploy() -> str:
    """The step-by-step deployment playbook."""
    return _read("docs/DEPLOYMENT.md")


@mcp.resource("recon://adapters")
def r_adapters() -> str:
    """The treasury/GL/DMS adapter contract + support matrix."""
    return _read("adapters/README.md")


@mcp.resource("recon://architecture")
def r_arch() -> str:
    """Pipeline, data model, and demo->enterprise mapping."""
    return _read("docs/ARCHITECTURE.md")


# ───────────── tools (actions) ─────────────
@mcp.tool()
def intake_status(path: str = "INTAKE.md") -> str:
    """Summarize a filled intake: ticked options, any remaining TBDs, and (if present) the adapter
    selection hints. Run this first to see what's chosen and what's still missing."""
    text = _read(path)
    if text.startswith("[missing]"):
        return text
    ticked = [ln.strip() for ln in text.splitlines() if "[x]" in ln.lower()]
    tbds = [ln.strip() for ln in text.splitlines() if "TBD" in ln]
    hints = [ln.strip() for ln in text.splitlines() if "Adapter selection" in ln or ("adapter" in ln.lower() and "->" in ln)]
    return json.dumps({
        "path": path, "ticked_options": len(ticked), "open_TBDs": tbds[:20],
        "adapter_hints": hints[:6],
        "note": "Fill every TBD before deploying; map ticked options to adapter keys via recon://adapters.",
    }, indent=2)


@mcp.tool()
def list_adapters() -> str:
    """List the available adapter keys per connection point (treasury / GL / DMS)."""
    import sys
    sys.path.insert(0, str(REPO))
    try:
        import adapters.gl, adapters.treasury, adapters.dms  # noqa: F401  (registers)
        from adapters.base import available
        return json.dumps({k: available(k) for k in ("treasury", "gl", "dms")}, indent=2)
    except Exception as e:  # noqa: BLE001
        return f"[error importing adapters] {e}\nSee {REPO / 'adapters' / 'README.md'} for the matrix."


@mcp.tool()
def scaffold_config(yaml_text: str) -> str:
    """Write stack/config.yaml from the adapter config you built off the intake (YAML text).
    Backs up any existing config. Secrets must be ${ENV_REFS}, never inline."""
    dest = STACK / "config.yaml"
    if dest.exists():
        (STACK / "config.yaml.bak").write_text(dest.read_text(encoding="utf-8"), encoding="utf-8")
    dest.write_text(yaml_text, encoding="utf-8")
    return f"wrote {dest} ({len(yaml_text)} bytes). Review, then stack('up')."


@mcp.tool()
def stack(action: str = "status") -> str:
    """Manage the deployable stack via docker compose in stack/. action: up | down | status | logs | build."""
    cmds = {
        "up": ["docker", "compose", "up", "-d", "--build"],
        "down": ["docker", "compose", "down"],
        "status": ["docker", "compose", "ps"],
        "logs": ["docker", "compose", "logs", "--tail", "40"],
        "build": ["docker", "compose", "build"],
    }
    if action not in cmds:
        return f"unknown action '{action}'. Use: {', '.join(cmds)}"
    return _sh(cmds[action], cwd=STACK, timeout=600 if action in ("up", "build") else 60)


@mcp.tool()
def reconcile() -> str:
    """Run the reconciliation engine for the current period (POST /api/reconcile) — pulls GL +
    statement balances through the wired adapters, matches within tolerance, writes the board."""
    return _http("/api/reconcile", method="POST", timeout=120)


@mcp.tool()
def verify_deploy() -> str:
    """Check the deployment is live: API health, KPIs, and a sample of the board."""
    return json.dumps({
        "health": _http("/api/health"),
        "kpis": _http("/api/kpis"),
        "accounts_sample": _http("/api/accounts")[:600],
    }, indent=2)


# ───────────── prompt (workflow) ─────────────
@mcp.prompt()
def deploy_recon(intake_path: str = "INTAKE.md") -> str:
    """End-to-end OpenRecon deployment from a filled intake."""
    return (
        f"Deploy OpenRecon from {intake_path}:\n"
        "1. Read recon://deployment-guide, recon://adapters, recon://architecture.\n"
        f"2. intake_status('{intake_path}') — confirm no TBDs; note the chosen treasury/GL/DMS adapters.\n"
        "3. list_adapters() — for any chosen stub (e.g. dynamics_gp, laserfiche), implement its one "
        "method in adapters/ per the comment (GL read-only; secrets from the store in INTAKE §H).\n"
        "4. scaffold_config(<yaml from the intake choices + account map>).\n"
        "5. stack('up'); verify_deploy(); then reconcile(); verify_deploy() again.\n"
        "6. Wire the UI to the API and harden for PROD (docs/PROMOTION.md). Never let real financials "
        "touch a demo/public tier."
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
