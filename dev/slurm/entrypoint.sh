#!/usr/bin/env bash
#
# Container entrypoint: bring up a complete one-node slurm cluster
# (munge + MariaDB + slurmdbd + slurmctld + slurmd, with a registered
# accounting association), then exec the command passed to ``docker run``
# (default: an interactive bash shell).
#
# Runs as root inside the container, so no sudo is needed. Must be run in a
# container with writable cgroups (``--privileged``); see cgroup_prep.sh.
set -euo pipefail

SETUP_DIR=/opt/slurm-setup
HOST="$(hostname -s)"
DB_PASS="${SLURM_DB_PASS:-slurmpw}"
# Users that should own a slurm association (so their jobs aren't rejected
# with InvalidAccount). Whoever runs the tests must be in this list; tests in
# the image run as root.
SLURM_ASSOC_USERS="${SLURM_ASSOC_USERS:-root}"

log() { echo "[entrypoint] $*"; }

# --- cgroup v2 delegation (no-op on a native systemd host) -----------------
bash "$SETUP_DIR/cgroup_prep.sh"

# --- munge (slurm's auth layer) --------------------------------------------
log "starting munge..."
install -d -m 0755 -o munge -g munge /run/munge          # 0755 so the slurm user can reach the socket
install -d -m 0700 -o munge -g munge /etc/munge /var/log/munge
if [[ ! -f /etc/munge/munge.key ]]; then
    dd if=/dev/urandom bs=1 count=1024 of=/etc/munge/munge.key 2>/dev/null
    chown munge:munge /etc/munge/munge.key
    chmod 0400 /etc/munge/munge.key
fi
runuser -u munge -- /usr/sbin/munged --force

# --- MariaDB (slurmdbd's backing store) ------------------------------------
log "starting MariaDB..."
install -d -o mysql -g mysql /run/mysqld /var/lib/mysql
if [[ ! -d /var/lib/mysql/mysql ]]; then
    mariadb-install-db --user=mysql --datadir=/var/lib/mysql >/dev/null 2>&1
fi
runuser -u mysql -- /usr/sbin/mariadbd --datadir=/var/lib/mysql \
    >/var/log/mariadb.log 2>&1 &
for _ in $(seq 1 30); do
    mysqladmin ping >/dev/null 2>&1 && break
    sleep 1
done
mysql <<SQL
CREATE DATABASE IF NOT EXISTS slurm_acct_db;
CREATE USER IF NOT EXISTS 'slurm'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL ON slurm_acct_db.* TO 'slurm'@'localhost';
FLUSH PRIVILEGES;
SQL

# --- render configs --------------------------------------------------------
install -d -m 0755 /etc/slurm
SLURM_NODE_HOST="$HOST" \
SLURM_STATE_DIR=/var/spool/slurm/ctld \
SLURM_SPOOL_DIR=/var/spool/slurm/d \
SLURM_RUN_DIR=/run \
SLURM_LOG_DIR=/var/log/slurm \
    bash "$SETUP_DIR/render_slurm_conf.sh" /etc/slurm/slurm.conf
sed -e "s|@STORAGE_PASS@|${DB_PASS}|g" \
    -e "s|@LOG_DIR@|/var/log/slurm|g" \
    -e "s|@RUN_DIR@|/run|g" \
    "$SETUP_DIR/slurmdbd.conf.tmpl" > /etc/slurm/slurmdbd.conf
chown slurm:slurm /etc/slurm/slurmdbd.conf
chmod 0600 /etc/slurm/slurmdbd.conf
# Inside a container slurm must manage cgroups itself (no systemd/dbus).
printf 'CgroupPlugin=autodetect\nIgnoreSystemd=yes\n' > /etc/slurm/cgroup.conf

# --- slurmdbd --------------------------------------------------------------
log "starting slurmdbd..."
slurmdbd
for _ in $(seq 1 20); do
    sacctmgr -i show cluster >/dev/null 2>&1 && break
    sleep 1
done

# --- slurmctld + slurmd ----------------------------------------------------
log "starting slurmctld + slurmd..."
slurmctld
sleep 1
# Launch slurmd from inside system.slice so its stepd scope lands in a
# delegated, controller-enabled cgroup.
echo $$ > /sys/fs/cgroup/system.slice/cgroup.procs 2>/dev/null || true
slurmd

# --- register the accounting association -----------------------------------
# slurmctld auto-registers the cluster with slurmdbd; we just add an account
# and the user(s) that will submit jobs.
log "registering accounting association for: ${SLURM_ASSOC_USERS}"
sacctmgr -i add account default Cluster=cmdq \
    Description="cmd_queue test account" 2>/dev/null || true
for u in $SLURM_ASSOC_USERS; do
    sacctmgr -i add user "$u" Account=default Cluster=cmdq 2>/dev/null || true
done

# --- wait for the node to be usable so the first sbatch doesn't race boot --
log "waiting for node to become available..."
for _ in $(seq 1 30); do
    if sinfo -h -o '%T' 2>/dev/null | grep -qE 'idle|mixed|alloc'; then
        break
    fi
    scontrol update nodename="$HOST" state=RESUME 2>/dev/null || true
    sleep 1
done

sinfo || true
log "cluster up; exec: $*"
exec "$@"
