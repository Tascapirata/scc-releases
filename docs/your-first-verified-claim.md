# SCC Runner Free 0.3.0 — Your First Verified Claim

This guide uses the supported local Free path. It does not require a Control
Plane, enrollment, S5-C, billing, or Managed.

The example checks whether a local systemd service is active. It observes the
service; it does not start, stop, restart, or modify it.

## A. Prerequisites

- Linux or WSL with a readable systemd user/system authority.
- Python 3.11 or newer.
- The verified SCC Runner 0.3.0 wheel.
- A systemd service name that you are allowed to observe, such as
  `cron.service`.

The installation artifact may need to be downloaded first. After installation,
this local check does not need a Control Plane.

## B. Install

From the directory containing the wheel:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --no-index --no-deps ./scc_runner-0.3.0-py3-none-any.whl
scc --version
```

Expected version output:

```text
scc 0.3.0
```

## C. Choose a service

Replace `<YOUR_SERVICE>` with a local unit you can read. Do not use a service
whose state you must change to make the check pass.

For the observed run, the service was `cron.service`.

## D. Create the check

```bash
scc create-check \
  --id service-active \
  --name "Service active" \
  --claim "The <YOUR_SERVICE> service is active" \
  --locator <YOUR_SERVICE> \
  --field ActiveState \
  --expected active \
  --output service-active.toml
```

The command should report `CREATE_CHECK=PASS` and write a version-1 TOML
check.

## E. Run and read SCC

```bash
scc check service-active.toml --runs-dir runs
```

The observed successful run reported:

```text
CHECK=...
CASE=CHECK-cron-active
VERDICT=CONFIRMADO
RULE=RULE-CHECK-CONFIRMED
STOP_REASON=SUFFICIENT_EVIDENCE
REPORT=<timestamped report.json path>
```

Open the `REPORT=` path. It contains the claim, `systemd` authority,
`systemd-properties` observation, evidence ID, observation SHA-256, run ID,
ledger root hash, and verdict. The verdict is limited to the configured
`ActiveState` property.

## F. Run it again

```bash
scc check service-active.toml --runs-dir runs
```

The second run creates another timestamped report and verifies the same claim
again. This is the repeatable Free value: rerun after a deployment or system
change and retain evidence of the observed state.

## G. Common failure

If the unit name is wrong or inactive, the observed nonexistent-unit example
returned:

```text
VERDICT=FALSADO
RULE=RULE-CHECK-FALSIFIED
STOP_REASON=SUFFICIENT_EVIDENCE
```

Check the configured locator in the report, correct it with `scc create-check`,
and run the check again. The current output is actionable but does not provide
a dedicated “unit not found” diagnostic.

Claim Ladder, G9, and G10 are not required for this first basic verdict.
Managed is not required and is not part of this guide.

