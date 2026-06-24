#!/usr/bin/env bash
#
# Render ``slurm.conf.tmpl`` into a concrete ``slurm.conf`` for the machine
# this runs on. Shared by the native setup script and the Docker entrypoint
# so both produce an identical, correct config.
#
# Usage:
#   render_slurm_conf.sh OUTPUT_PATH
#
# Honors these optional environment overrides (sensible defaults otherwise):
#   SLURM_NODE_HOST   node + control hostname        (default: `hostname -s`)
#   SLURM_CPUS        CPUs the node advertises        (default: `nproc`)
#   SLURM_REALMEM_MB  RealMemory in MB                (default: ~85% of total)
#   SLURM_STATE_DIR   StateSaveLocation               (default: /var/spool/slurm/ctld)
#   SLURM_SPOOL_DIR   SlurmdSpoolDir                  (default: /var/spool/slurm/d)
#   SLURM_RUN_DIR     pid file dir                    (default: /run)
#   SLURM_LOG_DIR     log dir                         (default: /var/log/slurm)
set -euo pipefail

OUT_PATH="${1:?usage: render_slurm_conf.sh OUTPUT_PATH}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMPL="$HERE/slurm.conf.tmpl"

host="${SLURM_NODE_HOST:-$(hostname -s)}"
cpus="${SLURM_CPUS:-$(nproc)}"

if [[ -n "${SLURM_REALMEM_MB:-}" ]]; then
    mem="$SLURM_REALMEM_MB"
else
    # Advertise ~85% of physical RAM so slurm never flags the node as
    # over-reporting memory (which would mark it invalid/down).
    total_mb=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)
    mem=$(( total_mb * 85 / 100 ))
    [[ "$mem" -lt 64 ]] && mem=64
fi

state_dir="${SLURM_STATE_DIR:-/var/spool/slurm/ctld}"
spool_dir="${SLURM_SPOOL_DIR:-/var/spool/slurm/d}"
run_dir="${SLURM_RUN_DIR:-/run}"
log_dir="${SLURM_LOG_DIR:-/var/log/slurm}"

sed \
    -e "s|@HOSTNAME@|${host}|g" \
    -e "s|@CPUS@|${cpus}|g" \
    -e "s|@MEM@|${mem}|g" \
    -e "s|@STATE_DIR@|${state_dir}|g" \
    -e "s|@SPOOL_DIR@|${spool_dir}|g" \
    -e "s|@RUN_DIR@|${run_dir}|g" \
    -e "s|@LOG_DIR@|${log_dir}|g" \
    "$TMPL" > "$OUT_PATH"

echo "[render_slurm_conf] wrote $OUT_PATH (host=$host cpus=$cpus mem=${mem}MB)"
