#!/usr/bin/env bash
#
# Build the single-node slurm image and run cmd_queue's slurm backend tests
# inside it, against the *current working tree* (mounted read-write at /io).
#
#   dev/slurm/run_slurm_tests_in_docker.sh                 # run the slurm exec tests
#   dev/slurm/run_slurm_tests_in_docker.sh shell           # drop into a shell in the cluster
#   dev/slurm/run_slurm_tests_in_docker.sh pytest -k slurm # run an arbitrary pytest invocation
#
# The image boots munge + slurmctld + slurmd (see entrypoint.sh) before the
# command runs, so ``SlurmQueue.is_available()`` is True inside the container.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../.." && pwd)"
IMAGE=cmd_queue-slurm

echo "[run_slurm_tests_in_docker] building $IMAGE ..."
docker build -f "$HERE/Dockerfile" -t "$IMAGE" "$HERE"

# Install the repo (editable) into the container, then run the requested
# command. Default to the slurm-specific execution tests.
inner_cmd='pytest tests/test_backend_execution.py tests/test_slurm_variants.py -v -k slurm'
if [[ "${1:-}" == "shell" ]]; then
    inner_cmd='exec bash'
elif [[ $# -gt 0 ]]; then
    inner_cmd="$*"
fi

echo "[run_slurm_tests_in_docker] running: $inner_cmd"
# --privileged is required so the entrypoint can delegate cgroup v2 controllers
# for slurmd (see cgroup_prep.sh). -t only when attached to a TTY.
tty_flags=(-i)
[[ -t 0 && -t 1 ]] && tty_flags=(-it)
docker run --rm "${tty_flags[@]}" \
    --privileged \
    -v "$REPO_ROOT:/io" \
    -w /io \
    "$IMAGE" \
    bash -lc "
        set -e
        python3 -m pip install --quiet --break-system-packages -e '.[tests]' 2>/dev/null \
            || python3 -m pip install --quiet --break-system-packages -e .
        $inner_cmd
    "
