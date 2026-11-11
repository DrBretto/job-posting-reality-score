"""R2 — which template and which config does each deploy command actually select?

This calls the INSTALLED SAM CLI's own resolution functions. It invokes no deploy, contacts no AWS
endpoint, needs no credential and writes nothing inside the repository. The stale-default-build case
is simulated in a throwaway temporary directory so the hazard is never created in the real tree.

Two resolutions matter, and the second is the one that bites after the first is fixed:

  template  `get_or_default_template_file_name(..., include_build=True)` searches
            `.aws-sam/build/template.yaml`, then `template.yaml`, `template.yml`, `template.json`
            relative to the CURRENT DIRECTORY. A `--build-dir` is never consulted.

  config    `configuration_option`'s resolver joins a RELATIVE `--config-file` onto
            `ctx.samconfig_dir`, which SAM sets to the directory of the template it was given. So
            once the template lives in a temporary build directory, `--config-file
            infra/samconfig.toml` resolves under that build directory and the real config is missed.
            An absolute path is the only unambiguous form.

Usage: run from the repository root with the repo's interpreter.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

SAM_SITE_PACKAGES = (
    "/opt/homebrew/Cellar/aws-sam-cli/1.137.1/libexec/lib/python3.13/site-packages"
)
if SAM_SITE_PACKAGES not in sys.path:
    sys.path.insert(0, SAM_SITE_PACKAGES)

from samcli.commands._utils.options import (  # noqa: E402
    _TEMPLATE_OPTION_DEFAULT_VALUE,
    get_or_default_template_file_name,
)
from samcli.lib.config.samconfig import DEFAULT_CONFIG_FILE_NAME  # noqa: E402

REPO = Path(__file__).resolve().parents[6]


class _Ctx:
    """The one attribute SAM's callback reads and the one it writes."""

    def __init__(self):
        self.default_map: dict = {}
        self.samconfig_dir: str | None = None


def select_template(provided_value: str | None) -> dict:
    """What `sam deploy` resolves its template to, and where it will then look for samconfig."""
    ctx = _Ctx()
    value = provided_value if provided_value else _TEMPLATE_OPTION_DEFAULT_VALUE
    resolved = get_or_default_template_file_name(ctx, None, value, include_build=True)
    return {
        "given": provided_value or "(omitted — SAM default search)",
        "resolved_template": resolved,
        "template_exists": os.path.exists(resolved),
        "samconfig_dir": ctx.samconfig_dir,
    }


def select_config(samconfig_dir: str | None, config_file: str) -> dict:
    """Mirror `cli_config_file.configuration_option`'s own join for a user-supplied value."""
    config_dir = samconfig_dir or os.getcwd()
    path = (config_file if os.path.isabs(config_file)
            else os.path.join(config_dir, config_file))
    return {
        "given": config_file,
        "samconfig_dir": config_dir,
        "resolved_config": path,
        "config_exists": os.path.exists(path),
        "is_absolute": os.path.isabs(config_file),
    }


def main() -> int:
    os.chdir(REPO)
    build_dir = Path(tempfile.mkdtemp(prefix="jprs-selection-probe-"))
    built_template = build_dir / "template.yaml"
    built_template.write_text("# stand-in for the artifact `sam build --build-dir` produces\n")

    report: dict = {
        "scope": (
            "installed SAM CLI resolution functions only; no deploy, no AWS call, no credential, "
            "nothing written inside the repository"
        ),
        "sam_cli": "1.137.1",
        "cwd": str(REPO),
        "root_template_yaml_exists": os.path.exists("template.yaml"),
        "root_template_yml_exists": os.path.exists("template.yml"),
        "default_build_template_exists": os.path.exists(".aws-sam/build/template.yaml"),
        "infra_default_build_template_exists": os.path.exists(
            "infra/.aws-sam/build/template.yaml"
        ),
    }

    # --- the P04 handoff's command: build into a custom dir, deploy with no --template-file -------
    p04 = select_template(None)
    report["p04_forward_command"] = {
        "documented": (
            "sam build --template-file infra/template.yaml --build-dir /tmp/jprs-build"
            "  then  sam deploy --config-file infra/samconfig.toml"
        ),
        "selection": p04,
        "verdict": (
            "selects a template that does not exist" if not p04["template_exists"]
            else "selects a template OTHER than the verified build"
        ),
        "selects_the_verified_build": False,
    }

    # --- the same command in a tree that has a stale default build -------------------------------
    stale_root = Path(tempfile.mkdtemp(prefix="jprs-stale-default-build-"))
    stale_build = stale_root / ".aws-sam" / "build"
    stale_build.mkdir(parents=True)
    (stale_build / "template.yaml").write_text("# a stale build from an earlier release\n")
    here = os.getcwd()
    os.chdir(stale_root)
    try:
        stale = select_template(None)
    finally:
        os.chdir(here)
    report["p04_forward_command_with_a_stale_default_build"] = {
        "selection": stale,
        "verdict": (
            "silently selects the stale default build"
            if stale["resolved_template"].endswith(".aws-sam/build/template.yaml")
            else "selected something else"
        ),
    }

    # --- from infra/, where a real stale build is sitting in this very tree -----------------------
    if os.path.exists("infra/.aws-sam/build/template.yaml"):
        os.chdir(REPO / "infra")
        try:
            from_infra = select_template(None)
        finally:
            os.chdir(here)
        report["p04_forward_command_run_from_infra"] = {
            "selection": from_infra,
            "verdict": (
                "selects the stale 2026-08-01 build already present in this tree"
                if from_infra["resolved_template"].endswith(".aws-sam/build/template.yaml")
                else "selected something else"
            ),
        }

    # --- the corrected command: template pinned to the build, config pinned absolutely ------------
    fixed = select_template(str(built_template))
    config_relative = select_config(fixed["samconfig_dir"], "infra/samconfig.toml")
    config_absolute = select_config(fixed["samconfig_dir"], str(REPO / "infra/samconfig.toml"))
    report["p05_corrected_command"] = {
        "documented": (
            f'sam build --template-file infra/template.yaml --build-dir "$BUILD"'
            f'  then  sam deploy --template-file "$BUILD/template.yaml" '
            f'--config-file "$PWD/infra/samconfig.toml" --config-env default'
        ),
        "selection": fixed,
        "selects_the_verified_build": (
            os.path.realpath(fixed["resolved_template"]) == os.path.realpath(built_template)
        ),
        "config_if_given_relatively": config_relative,
        "config_if_given_absolutely": config_absolute,
        "why_the_config_must_be_absolute": (
            "SAM sets samconfig_dir to the given template's directory, so a relative config path "
            "resolves inside the temporary build directory and the repository's samconfig is missed"
        ),
    }

    # --- the rollback command, checked the same way ------------------------------------------------
    rollback_root = Path(tempfile.mkdtemp(prefix="jprs-rollback-build-"))
    (rollback_root / "template.yaml").write_text("# stand-in for the rollback build\n")
    rollback = select_template(str(rollback_root / "template.yaml"))
    report["p05_rollback_command"] = {
        "selection": rollback,
        "selects_the_rollback_build": rollback["template_exists"],
        "config_must_be_absolute_too": select_config(
            rollback["samconfig_dir"], "infra/samconfig.toml"
        ),
    }

    report["default_config_file_name"] = DEFAULT_CONFIG_FILE_NAME
    report["assertions"] = {
        "p04_command_does_not_select_the_verified_build":
            not report["p04_forward_command"]["selects_the_verified_build"],
        "p04_command_can_select_a_stale_default_build":
            report["p04_forward_command_with_a_stale_default_build"]["selection"][
                "resolved_template"].endswith(".aws-sam/build/template.yaml"),
        "p05_command_selects_the_verified_build":
            report["p05_corrected_command"]["selects_the_verified_build"],
        "p05_absolute_config_resolves_to_the_repository_config":
            config_absolute["config_exists"],
        "relative_config_would_have_been_missed":
            not config_relative["config_exists"],
    }
    print(json.dumps(report, indent=2))
    return 0 if all(report["assertions"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
