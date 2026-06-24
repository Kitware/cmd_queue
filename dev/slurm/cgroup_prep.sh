#!/usr/bin/env bash
#
# Prepare cgroup v2 for slurmd *inside a container*. Slurm 23.11's slurmd
# always initializes a cgroup plugin; in a stock container the cgroup2 root
# has no delegated controllers and no ``system.slice``, so slurmd dies with
# "cannot create cgroup context for cgroup/v2".
#
# This does the standard cgroup-v2 delegation dance:
#   1. move every process out of the cgroup root into a leaf (the no-internal-
#      process rule forbids enabling controllers while procs live in the root);
#   2. delegate all available controllers into the root's subtree;
#   3. create the ``system.slice`` that slurm (with IgnoreSystemd=yes) expects
#      to create its ``<host>_slurmstepd.scope`` under.
#
# Pair this with a ``cgroup.conf`` containing ``IgnoreSystemd=yes`` (so slurm
# manages cgroups directly instead of asking a non-existent systemd/dbus).
#
# Requires a writable cgroup2 fs -- run the container with ``--privileged``
# (or equivalent cgroup delegation). On a native systemd host none of this is
# needed (systemd handles delegation), so this script is a no-op there.
set -euo pipefail

CG=/sys/fs/cgroup

if [[ ! -f "$CG/cgroup.controllers" ]]; then
    echo "[cgroup_prep] no cgroup2 at $CG (or already prepared); skipping"
    exit 0
fi

# 1. Move all processes into a leaf so the root has no internal processes.
mkdir -p "$CG/init"
while read -r pid; do
    echo "$pid" > "$CG/init/cgroup.procs" 2>/dev/null || true
done < "$CG/cgroup.procs"

# 2. Delegate every controller the kernel exposes into the subtree.
add=""
for c in $(cat "$CG/cgroup.controllers"); do
    add="$add +$c"
done
echo "$add" > "$CG/cgroup.subtree_control" 2>/dev/null || true

# 3. Pre-create the slice slurm's stepd scope is nested under.
mkdir -p "$CG/system.slice"

echo "[cgroup_prep] delegated controllers:$(cat "$CG/cgroup.subtree_control")"
