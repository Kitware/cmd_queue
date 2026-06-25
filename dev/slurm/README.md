# Single-node Slurm for testing the slurm backend

cmd_queue's slurm backend is normally untested on dev machines: the execution
tests in `tests/test_backend_execution.py` (and `SlurmQueue.is_available()`)
**skip** unless a working slurm controller + compute node is reachable. This
folder stands up a tiny one-node cluster so those tests actually run.

Two ways to use it:

| Path | Isolation | Use when |
| --- | --- | --- |
| **Docker** (`run_slurm_tests_in_docker.sh`) | full | you just want to run the slurm tests; recommended |
| **Native** (`setup_slurm_local.sh`) | none — modifies this host | you want slurm running directly on the VM |

## Docker (recommended)

Builds an image that boots munge + MariaDB + slurmdbd + slurmctld + slurmd,
registers an accounting association, then runs the tests against your current
working tree (mounted at `/io`):

```bash
dev/slurm/run_slurm_tests_in_docker.sh                 # run the slurm tests
dev/slurm/run_slurm_tests_in_docker.sh shell           # interactive shell in the cluster
dev/slurm/run_slurm_tests_in_docker.sh pytest -k slurm # arbitrary pytest invocation
```

It runs the container `--privileged` so the entrypoint can delegate cgroup v2
controllers to slurmd (see `cgroup_prep.sh`). Inside the container:

```bash
sinfo                       # node should be 'idle'
sbatch --wrap 'echo hi'     # submits and runs
```

## Native (this VM)

```bash
dev/slurm/setup_slurm_local.sh           # install + configure + start (uses sudo)
dev/slurm/setup_slurm_local.sh status    # sinfo / squeue / associations
dev/slurm/setup_slurm_local.sh stop      # stop the daemons
dev/slurm/setup_slurm_local.sh teardown  # stop + remove the slurm config
```

This installs and starts system services (slurm, slurmdbd, munge, MariaDB) on
the host — it is meaningfully invasive. It registers an association for the
user who invoked `sudo` (override with `SLURM_ASSOC_USER=...`). After setup:

```bash
sinfo
python -m pytest tests/test_backend_execution.py -v -k slurm
```

## Why slurmdbd + MariaDB?

Slurm 23.11 (Ubuntu 24.04) deprecated `accounting_storage/none`. Without a
slurmdbd association, every submitted job is rejected with
`Reason=InvalidAccount` and never runs. The smallest reliable single-node
setup therefore includes a local MariaDB + slurmdbd and one registered
`default` account / user association.

## Files

| File | Purpose |
| --- | --- |
| `slurm.conf.tmpl` | single-node `slurm.conf` template (shared) |
| `slurmdbd.conf.tmpl` | `slurmdbd.conf` template (shared) |
| `render_slurm_conf.sh` | fills the slurm.conf template for the local host |
| `cgroup_prep.sh` | cgroup v2 delegation for slurmd inside a container |
| `Dockerfile` / `entrypoint.sh` | the containerised cluster |
| `run_slurm_tests_in_docker.sh` | build the image + run the tests |
| `setup_slurm_local.sh` | native (systemd) install/configure/start |
