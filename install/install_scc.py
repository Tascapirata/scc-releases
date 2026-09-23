#!/usr/bin/env python3
"""Verified local installer for SCC Runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from email.parser import Parser
from pathlib import Path
import re
import shutil
import subprocess
import sys
from zipfile import BadZipFile, ZipFile


class InstallerError(RuntimeError):
    pass


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def sha256(path: Path) -> str:
    digest=hashlib.sha256()

    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def wheel_metadata(
    wheel_path: Path,
) -> tuple[dict[str,str],dict[str,str]]:
    try:
        with ZipFile(wheel_path) as wheel:
            metadata_name=next(
                name
                for name in wheel.namelist()
                if name.endswith(
                    ".dist-info/METADATA"
                )
            )

            metadata=Parser().parsestr(
                wheel.read(
                    metadata_name
                ).decode("utf-8")
            )

            entry_name=next(
                (
                    name
                    for name in wheel.namelist()
                    if name.endswith(
                        ".dist-info/entry_points.txt"
                    )
                ),
                None,
            )

            entries={}

            if entry_name:
                section=None

                for raw in wheel.read(
                    entry_name
                ).decode("utf-8").splitlines():
                    line=raw.strip()

                    if (
                        line.startswith("[")
                        and line.endswith("]")
                    ):
                        section=line[1:-1]

                    elif (
                        section=="console_scripts"
                        and "=" in line
                    ):
                        key,value=line.split(
                            "=",
                            1,
                        )

                        entries[
                            key.strip()
                        ]=value.strip()

            return (
                {
                    "name":
                        metadata.get(
                            "Name",
                            "",
                        ),
                    "version":
                        metadata.get(
                            "Version",
                            "",
                        ),
                    "requires_python":
                        metadata.get(
                            "Requires-Python",
                            "",
                        ),
                },
                entries,
            )

    except (
        BadZipFile,
        StopIteration,
        UnicodeDecodeError,
    ) as exc:
        raise InstallerError(
            f"invalid wheel: {exc}"
        ) from exc


def python_requirement_ok(
    requirement: str,
) -> bool:
    match=re.fullmatch(
        r">=\s*(\d+)\.(\d+)(?:\.(\d+))?",
        requirement.strip(),
    )

    if not match:
        raise InstallerError(
            "unsupported Requires-Python"
        )

    wanted=tuple(
        int(value or 0)
        for value in match.groups()
    )

    return (
        sys.version_info[:3]
        >= wanted
    )


def preconditions() -> Path:
    if not sys.platform.startswith("linux"):
        raise InstallerError(
            "unsupported platform"
        )

    if sys.version_info < (3,11):
        raise InstallerError(
            "Python >= 3.11 required"
        )

    for command in (
        "curl",
        "sha256sum",
    ):
        if shutil.which(command) is None:
            raise InstallerError(
                f"required command missing: {command}"
            )

    home_text=os.environ.get(
        "HOME",
        "",
    ).strip()

    if not home_text:
        raise InstallerError(
            "HOME is not defined"
        )

    home=Path(
        home_text
    ).expanduser().absolute()

    return home


def verify_bundle(
    bundle: Path,
    expected_version: str,
) -> tuple[dict,Path,str]:
    manifest_path=(
        bundle
        / "release-manifest.json"
    )

    sums_path=(
        bundle
        / "SHA256SUMS"
    )

    try:
        manifest=json.loads(
            manifest_path.read_text(
                encoding="utf-8"
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ) as exc:
        raise InstallerError(
            "invalid release manifest"
        ) from exc

    if manifest.get(
        "schema_version"
    ) != 1:
        raise InstallerError(
            "unsupported manifest schema"
        )

    try:
        package=manifest["package"]
        source=manifest["source"]
        artifact=manifest["artifact"]

        filename=artifact["filename"]
        declared_sha=artifact["sha256"]
        declared_size=int(
            artifact["size_bytes"]
        )

    except (
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise InstallerError(
            "incomplete release manifest"
        ) from exc

    if package.get("name") != "scc-runner":
        raise InstallerError(
            "unexpected package name"
        )

    if (
        package.get("version")
        != expected_version
    ):
        raise InstallerError(
            "unexpected package version"
        )

    requirement=package.get(
        "requires_python",
        "",
    )

    if not python_requirement_ok(
        requirement
    ):
        raise InstallerError(
            "Python version incompatible"
        )

    commit=str(
        source.get(
            "commit",
            "",
        )
    )

    if (
        len(commit) != 40
        or any(
            c not in
            "0123456789abcdefABCDEF"
            for c in commit
        )
    ):
        raise InstallerError(
            "invalid source commit"
        )

    if (
        not isinstance(filename,str)
        or Path(filename).name != filename
        or not filename.endswith(".whl")
    ):
        raise InstallerError(
            "invalid wheel filename"
        )

    wheel=(
        bundle
        / filename
    )

    if not wheel.is_file():
        raise InstallerError(
            "wheel missing"
        )

    if wheel.stat().st_size != declared_size:
        raise InstallerError(
            "wheel size mismatch"
        )

    actual_sha=sha256(
        wheel
    )

    if actual_sha != declared_sha:
        raise InstallerError(
            "wheel SHA256 mismatch"
        )

    expected_sums=(
        f"{actual_sha}  {filename}\n"
    )

    try:
        actual_sums=sums_path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        raise InstallerError(
            "SHA256SUMS missing"
        ) from exc

    if actual_sums != expected_sums:
        raise InstallerError(
            "SHA256SUMS mismatch"
        )

    metadata,entries=wheel_metadata(
        wheel
    )

    expected_metadata={
        "name":
            package["name"],
        "version":
            package["version"],
        "requires_python":
            package["requires_python"],
    }

    if metadata != expected_metadata:
        raise InstallerError(
            "wheel metadata mismatch"
        )

    if (
        entries.get("scc")
        != "scc_runner.cli:main"
    ):
        raise InstallerError(
            "scc entrypoint mismatch"
        )

    if (
        entries.get("scc-runner")
        != "scc_runner.cli:main"
    ):
        raise InstallerError(
            "scc-runner entrypoint mismatch"
        )

    print("MANIFEST_VERIFY=PASS")
    print("SHA256_VERIFY=PASS")
    print("WHEEL_METADATA_VERIFY=PASS")

    return (
        manifest,
        wheel,
        actual_sha,
    )


def paths(
    home: Path,
) -> tuple[Path,Path]:
    xdg_data=os.environ.get(
        "XDG_DATA_HOME"
    )

    if xdg_data:
        data_root=(
            Path(xdg_data)
            .expanduser()
            .absolute()
            / "scc"
        )
    else:
        data_root=(
            home
            / ".local"
            / "share"
            / "scc"
        )

    bin_dir=(
        home
        / ".local"
        / "bin"
    )

    return (
        data_root,
        bin_dir,
    )


def managed_command_target(
    data_root: Path,
    name: str,
) -> Path:
    return (
        data_root
        / "current"
        / "venv"
        / "bin"
        / name
    )


def ensure_activation_slots(
    data_root: Path,
    bin_dir: Path,
) -> None:
    current=(
        data_root
        / "current"
    )

    releases=(
        data_root
        / "releases"
    ).absolute()

    if lexists(current):
        if not current.is_symlink():
            raise InstallerError(
                "unmanaged current runtime"
            )

        raw=Path(
            os.readlink(current)
        )

        if raw.is_absolute():
            target=raw
        else:
            target=(
                current.parent
                / raw
            )

        target=target.resolve(
            strict=False
        )

        if (
            target != releases
            and releases not in target.parents
        ):
            raise InstallerError(
                "current points outside managed releases"
            )

    for name in (
        "scc",
        "scc-runner",
    ):
        command=(
            bin_dir
            / name
        )

        target=managed_command_target(
            data_root,
            name,
        )

        if not lexists(command):
            continue

        if (
            not command.is_symlink()
            or os.readlink(command)
            != str(target)
        ):
            raise InstallerError(
                f"unmanaged command present: {command}"
            )


def run_checked(
    argv: list[str],
) -> str:
    result=subprocess.run(
        argv,
        text=True,
        capture_output=True,
    )

    if result.returncode:
        detail=(
            result.stderr.strip()
            or result.stdout.strip()
            or "command failed"
        )

        raise InstallerError(
            detail
        )

    return (
        result.stdout
        + result.stderr
    )


def smoke(
    release_dir: Path,
    expected_version: str,
) -> None:
    scc=(
        release_dir
        / "venv"
        / "bin"
        / "scc"
    )

    if not scc.is_file():
        raise InstallerError(
            "installed scc executable missing"
        )

    version_output=run_checked(
        [
            str(scc),
            "--version",
        ]
    )

    if (
        f"scc {expected_version}"
        not in version_output
    ):
        raise InstallerError(
            "installed version mismatch"
        )

    run_checked(
        [
            str(scc),
            "--help",
        ]
    )

    enroll_help=run_checked(
        [
            str(scc),
            "cloud",
            "enroll",
            "--help",
        ]
    )

    for argument in (
        "--url",
        "--token",
        "--name",
    ):
        if argument not in enroll_help:
            raise InstallerError(
                f"cloud enroll missing {argument}"
            )

    print("SCC_COMMAND=PASS")
    print(
        "SCC_CLOUD_ENROLL_COMMAND=PASS"
    )


def atomic_symlink(
    target: Path,
    link: Path,
) -> None:
    temporary=link.with_name(
        f".{link.name}.tmp-{os.getpid()}"
    )

    if lexists(temporary):
        temporary.unlink()

    os.symlink(
        str(target),
        temporary,
    )

    os.replace(
        temporary,
        link,
    )


def activate(
    data_root: Path,
    bin_dir: Path,
    release_dir: Path,
) -> None:
    data_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    bin_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    current=(
        data_root
        / "current"
    )

    old_target=None
    old_present=False

    if lexists(current):
        old_present=True
        old_target=os.readlink(
            current
        )

    try:
        atomic_symlink(
            release_dir,
            current,
        )

        for name in (
            "scc",
            "scc-runner",
        ):
            command=(
                bin_dir
                / name
            )

            if lexists(command):
                continue

            atomic_symlink(
                managed_command_target(
                    data_root,
                    name,
                ),
                command,
            )

    except Exception:
        if old_present:
            restore=current.with_name(
                f".current.restore-{os.getpid()}"
            )

            if lexists(restore):
                restore.unlink()

            os.symlink(
                old_target,
                restore,
            )

            os.replace(
                restore,
                current,
            )

        elif lexists(current):
            current.unlink()

        raise


def install_bundle(
    bundle: Path,
    expected_version: str,
) -> str:
    home=preconditions()

    manifest,wheel,digest=verify_bundle(
        bundle,
        expected_version,
    )

    data_root,bin_dir=paths(
        home
    )

    ensure_activation_slots(
        data_root,
        bin_dir,
    )

    release_dir=(
        data_root
        / "releases"
        / expected_version
        / digest
    )

    if release_dir.exists():
        smoke(
            release_dir,
            expected_version,
        )

        activate(
            data_root,
            bin_dir,
            release_dir,
        )

        return "ALREADY_INSTALLED"

    release_dir.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Python virtual environments are not relocatable:
    # console-script shebangs contain the absolute interpreter path.
    #
    # Build directly at the final immutable release path while it is
    # still inactive. ACTIVATE happens only after smoke passes.
    release_dir.mkdir()

    stage=release_dir

    try:
        venv_dir=(
            stage
            / "venv"
        )

        run_checked(
            [
                sys.executable,
                "-m",
                "venv",
                str(venv_dir),
            ]
        )

        python=(
            venv_dir
            / "bin"
            / "python"
        )

        run_checked(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--no-index",
                "--no-deps",
                str(wheel),
            ]
        )

        shutil.copy2(
            bundle
            / "release-manifest.json",
            stage
            / "release-manifest.json",
        )

        shutil.copy2(
            bundle
            / "SHA256SUMS",
            stage
            / "SHA256SUMS",
        )

        (
            stage
            / "source.json"
        ).write_text(
            json.dumps(
                manifest["source"],
                sort_keys=True,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        smoke(
            stage,
            expected_version,
        )

    except Exception:
        if stage.exists():
            shutil.rmtree(
                stage,
                ignore_errors=True,
            )

        raise

    activate(
        data_root,
        bin_dir,
        release_dir,
    )

    return "INSTALLED"


def main(
    argv: list[str] | None = None,
) -> int:
    parser=argparse.ArgumentParser(
        prog="install_scc"
    )

    sub=parser.add_subparsers(
        dest="command",
        required=True,
    )

    install=sub.add_parser(
        "install-bundle"
    )

    install.add_argument(
        "--bundle",
        required=True,
        type=Path,
    )

    install.add_argument(
        "--expected-version",
        required=True,
    )

    args=parser.parse_args(
        argv
    )

    try:
        result=install_bundle(
            args.bundle.expanduser().absolute(),
            args.expected_version,
        )

    except (
        InstallerError,
        OSError,
    ) as exc:
        print(
            f"ERROR={exc}",
            file=sys.stderr,
        )

        print("INSTALL=FAIL")

        return 1

    print(
        f"INSTALL_RESULT={result}"
    )

    print("INSTALL=PASS")
    print(
        "INSTALL_WITHOUT_SUDO=PASS"
    )
    print(
        "INSTALL_WITHOUT_PYPI=PASS"
    )

    return 0


if __name__=="__main__":
    raise SystemExit(
        main()
    )
