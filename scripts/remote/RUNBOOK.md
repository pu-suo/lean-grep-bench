# Phase 8 — Remote Trace Runbook (AWS EC2)

This runbook is the EC2 counterpart to `phase_08_dojo_setup.md`. The Mac
operator never installs `lean-dojo` or the Lean toolchain locally; they
rent a Linux box, run the trace there, and rsync the JSONL artifacts back.
The Mac-side `leangrep-bench dojo validate`/`summarize` consume the
artifacts.

## Cost ceiling

`c7i.2xlarge` on-demand at us-east-1 list price is roughly $0.36/hr.
A 6-hour worst case is ~$2.20. Snapshot the EBS volume before terminating
if you might want to re-trace later without re-paying the build cost.

## Provision the instance

Pick a region with a recent c7i quota. Defaults below assume `us-east-1`.

- AMI: Ubuntu 24.04 LTS (HVM), x86_64.
- Instance type: `c7i.2xlarge` (8 vCPU, 16 GB RAM). Sized for headroom on
  Mathlib. Smaller instances (4 vCPU / 8 GB) will OOM during Mathlib
  elaboration; larger instances waste money on a 30-file project.
- Root volume: 80 GB gp3 (LeanDojo's `~/.cache/lean_dojo` is multi-GB,
  plus the toolchain).
- Security group: SSH (22) inbound from your IP only. No other ports.
- Key pair: existing or new; you'll need the `.pem` for ssh + rsync.

```sh
# Replace AMI_ID, KEY_NAME, SG_ID, SUBNET_ID with your values.
aws ec2 run-instances \
  --image-id ami-0XXXXXXXXXXXXXXXX \
  --instance-type c7i.2xlarge \
  --key-name KEY_NAME \
  --security-group-ids sg-XXXXXXXX \
  --subnet-id subnet-XXXXXXXX \
  --block-device-mappings 'DeviceName=/dev/sda1,Ebs={VolumeSize=80,VolumeType=gp3}' \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=leandojo-trace}]'
```

Grab the public DNS:

```sh
aws ec2 describe-instances \
  --filters Name=tag:Name,Values=leandojo-trace \
  --query 'Reservations[].Instances[].PublicDnsName' --output text
```

## Bootstrap the environment

SSH in once and install everything. All commands run as `ubuntu`.

```sh
ssh -i ~/.ssh/KEY_NAME.pem ubuntu@<public-dns>

sudo apt update && sudo apt install -y \
  git build-essential curl ca-certificates \
  python3.11 python3.11-venv python3.11-dev

# Lean toolchain (PFR pins leanprover/lean4:v4.28.0-rc1).
curl -sSf https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh | \
  sh -s -- -y --default-toolchain leanprover/lean4:v4.28.0-rc1
source "$HOME/.elan/env"

# Repo + venv.
git clone https://github.com/<your-fork>/lean-benchmark.git
cd lean-benchmark
python3.11 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dojo]"
pip install -r scripts/remote/requirements.txt
```

Optional: `export GITHUB_ACCESS_TOKEN=ghp_...` if you hit GitHub API rate
limits during the LeanDojo trace.

## Smoke test (do this before the full trace)

```sh
cd ~/lean-benchmark
source .venv/bin/activate
source "$HOME/.elan/env"

python scripts/remote/smoke_trace_pfr.py --file PFR/HomPFR.lean
```

Fallback files if `PFR/HomPFR.lean` is unsuitable for some reason:

- `PFR/SecondEstimate.lean` (5 apply/exact/use/refine calls)
- `PFR/EntropyPFR.lean` (3 calls; smallest file in the repo)

The PFR commit is pinned via the `PFR_PINNED_COMMIT` constant at the top
of [`scripts/remote/remote_trace_pfr.py`](../scripts/remote/remote_trace_pfr.py).
PFR force-pushes master from time to time; when an old commit gets orphaned
upstream, lean-dojo's `git checkout` fails with `fatal: reference is not a
tree`. Update the constant to current upstream HEAD
(`git ls-remote https://github.com/teorth/pfr HEAD`) and re-run.

The smoke run should complete in under 30 minutes (Mathlib needs to build
once; subsequent runs reuse the cache). Output goes to
`data/dojo_trace/_smoke.jsonl`.

On the Mac, pull and validate:

```sh
# From the Mac repo root:
rsync -avz --partial --append-verify \
  ubuntu@<public-dns>:~/lean-benchmark/data/dojo_trace/_smoke.jsonl \
  data/dojo_trace/

leangrep-bench dojo validate --trace data/dojo_trace/_smoke.jsonl
leangrep-bench dojo summarize --trace data/dojo_trace/_smoke.jsonl
head -1 data/dojo_trace/_smoke.jsonl | python -m json.tool | less
```

If `validate` fails: a field name in `scripts/remote/remote_trace_pfr.py`'s
`_to_trace` does not match what the installed lean-dojo exposes. Adjust the
attribute names there, push, `git pull` on the EC2 box, re-run the smoke
test. The schema itself is `extra="ignore"`, so adding fields is safe.

## Full trace

Run under `nohup` so an SSH disconnect does not kill it.

```sh
cd ~/lean-benchmark
source .venv/bin/activate
source "$HOME/.elan/env"

nohup python scripts/remote/remote_trace_pfr.py \
  --out-dir data/dojo_trace \
  > trace.log 2>&1 &

# Watch progress:
tail -f trace.log
```

Expected wall time: 3–6 hours on `c7i.2xlarge`. LeanDojo cites ~1 hr on
32 cores; this instance has 8.

The script is **resume-safe**: re-running with the same `--out-dir` skips
files already listed in `data/dojo_trace/_progress.json`. Per-file
failures land in `data/dojo_trace/_failures.json`; the script never aborts
on a single bad file.

## Periodic transfer (do not wait until the end)

EC2 instances can be terminated for many reasons. Rsync incrementally
during the trace. Run this on the Mac every ~30 min while the trace is
going:

```sh
rsync -avz --partial --append-verify \
  ubuntu@<public-dns>:~/lean-benchmark/data/dojo_trace/ \
  data/dojo_trace/
```

`--partial --append-verify` makes interrupted transfers resumable. The
sidecar files (`_progress.json`, `_failures.json`) come along too.

## Verify the full trace on the Mac

```sh
leangrep-bench dojo validate  --trace data/dojo_trace
leangrep-bench dojo summarize --trace data/dojo_trace
```

Expected: 5,000–20,000 tactic invocations across roughly 30 source files
(per the phase 8 spec). If the count is wildly outside that range,
investigate before moving to phase 9.

Paste one fully-rendered trace record into your phase wrap-up:

```sh
head -1 data/dojo_trace/PFR__HomPFR.lean.jsonl | python -m json.tool
```

## Teardown

```sh
# (Optional) snapshot the EBS volume so re-tracing is cheap later.
VOL_ID=$(aws ec2 describe-instances \
  --filters Name=tag:Name,Values=leandojo-trace \
  --query 'Reservations[].Instances[].BlockDeviceMappings[0].Ebs.VolumeId' \
  --output text)
aws ec2 create-snapshot --volume-id "$VOL_ID" --description "leandojo-trace post-run"

# Terminate.
INST_ID=$(aws ec2 describe-instances \
  --filters Name=tag:Name,Values=leandojo-trace \
  --query 'Reservations[].Instances[].InstanceId' --output text)
aws ec2 terminate-instances --instance-ids "$INST_ID"
```

## Troubleshooting

- **`elan` not found after install**: `source $HOME/.elan/env` (the
  installer adds it to `~/.profile` but you may have a non-login shell).
- **`lake exe cache get` complains about toolchain**: the local
  `lean-toolchain` file in PFR pins `v4.28.0-rc1`. If LeanDojo bumps PFR
  to a different commit with a newer toolchain, install that toolchain
  with `elan toolchain install <version>`.
- **Out of memory during Mathlib elaboration**: bump to `c7i.4xlarge`
  (32 GB RAM). The instance type can be changed in place by stopping →
  modify → starting.
- **Disk fills up**: bump the EBS volume to 160 GB and grow the
  filesystem (`sudo growpart /dev/nvme0n1 1 && sudo resize2fs
  /dev/nvme0n1p1`).
- **Trace stalls on one file forever**: kill the process. The
  `_progress.json` records what completed; re-run and the offending file
  is recorded in `_failures.json` if it raised, or you can pass
  `--max-files N` to bracket which file is the problem.

## What we deliberately do not do here

- **Ship the LeanDojo on-disk cache back to the Mac.** It is multi-GB and
  the Mac cannot read it without lean-dojo. Only the projected JSONL
  crosses the boundary.
- **Run a structured-goal parser on the trace box.** Phase 8 keeps
  `state_before_pp` / `state_after_pp` as raw strings; phase 9 does the
  parsing. This keeps the trace box's job narrow and reproducible.
