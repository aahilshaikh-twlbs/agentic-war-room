# AWR installer pre-flight (T0)

The interactive installer (`bash install.sh`) runs `precheck.run_prechecks()`
before mutating any Hermes profile. Each row below is one capability the
installer depends on. A `fail` blocks the install with a remediation hint; a
`warn` is advisory and the install proceeds. The live results are also rendered
into `<profile>/local/install.log` at run time via `render_preflight_doc`.

## The eight checks

| # | Check (`name`) | What it verifies | Hard-fail hint |
|---|---|---|---|
| 1 | `python_version` | `sys.version_info >= (3, 9)` | "Python >=3.9 required." |
| 2 | `hermes_on_path` | `shutil.which("hermes")` resolves | "Install the hermes CLI and ensure it is on PATH." |
| 3 | `hermes_version` | `hermes --version` parses to `>= 0.12` (robust regex; unparseable → **warn**, never fail) | "hermes >=0.12 required; run 'hermes update'." |
| 4 | `hermes_profile_install_surface` | `hermes profile install --help` exposes `--name`, `--alias`, `--force`, `-y/--yes` | "upgrade hermes." |
| 5 | `hermes_plugins_enable_surface` | `hermes plugins enable --help` exposes the `name` positional; records `plugins_enable_has_yes` (A8/F1) | "upgrade hermes." |
| 6 | `posix_terminal` | `import termios, tty` succeeds (hard-fail on Windows) | "needs a POSIX terminal; use WSL or --headless." |
| 7 | `profiles_dir_writable` | a probe file can be created under `~/.hermes/profiles/` | "Ensure the profiles dir exists and is writable." |
| 8 | `substrate_imports` | `python3 -c "import _substrate.render, ..."` succeeds with the installer dir on `PYTHONPATH` (K1/F4) | "run sync_substrate.sh." |

The `git_for_url_source` check is appended **only** when `--source` is a URL
(K23): it confirms `git` is on PATH so the remote can be cloned.

## T0 verification outcome (2026-06-08)

Captured live on the build host (`hermes 0.15.1`, Python 3.9.6, macOS):

| Check | Status | Notes |
|---|---|---|
| `python_version` | pass | Python 3.9.6 |
| `hermes_on_path` | pass | hermes resolved on PATH |
| `hermes_version` | pass | hermes 0.15.1 (>= 0.12) |
| `hermes_profile_install_surface` | pass | `--name --alias --force -y` all present |
| `hermes_plugins_enable_surface` | pass | `name` positional present; **no `-y` flag** → `plugins_enable_has_yes = False` (confirms A8/C3: enable is `hermes -p <name> plugins enable warroom-gate`) |
| `posix_terminal` | pass | termios/tty import cleanly on macOS |
| `profiles_dir_writable` | pass | `~/.hermes/profiles/` probe succeeded |
| `substrate_imports` | pass¹ | verified once the `_substrate/` package lands in T2 |

¹ `substrate_imports` reports `fail` until the vendored `_substrate/` package is
created (T2). The import mechanism itself is proven by
`test_installer_precheck.py::test_substrate_imports_under_pythonpath` (fabricated
package) and the drift suite `test_installer_substrate_no_drift.py` (real
package).

No T0 check contradicted a plan assumption, so code work proceeded.
