#!/usr/bin/env bash
#
# Set up a single-node Slurm cluster on *this* machine so the slurm backend
# tests actually run instead of skipping. Mirrors the Docker image
# (dev/slurm/Dockerfile) but uses the host's systemd to manage daemons.
#
# Targeted at Debian/Ubuntu (apt + the distro slurm-wlm/slurmdbd packages).
# It is idempotent: re-running re-renders config and restarts daemons. Needs
# root for install/config (re-execs under sudo).
#
#   dev/slurm/setup_slurm_local.sh           # install + configure + start
#   dev/slurm/setup_slurm_local.sh status    # show sinfo / squeue / sacctmgr
#   dev/slurm/setup_slurm_local.sh stop      # stop the slurm daemons
#   dev/slurm/setup_slurm_local.sh teardown  # stop + remove the slurm config
#
# NOTE: this installs and starts system services (slurm, slurmdbd, munge,
# MariaDB) on the host -- it is meaningfully invasive. Prefer the Docker path
# (run_slurm_tests_in_docker.sh) if you just want to run the tests in
# isolation. ``teardown`` removes the slurm config but intentionally leaves
# the installed packages and MariaDB data in place.
#
# After it finishes, verify with:
#   sinfo
#   python -c "import cmd_queue; print('slurm' in cmd_queue.Queue.available_backends())"
#   python -m pytest tests/test_backend_execution.py -v -k slurm
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ACTION="${1:-setup}"

CONF_DIR=/etc/slurm
CONF_PATH="$CONF_DIR/slurm.conf"
DBD_CONF_PATH="$CONF_DIR/slurmdbd.conf"
STATE_DIR=/var/spool/slurm/ctld
SPOOL_DIR=/var/spool/slurm/d
LOG_DIR=/var/log/slurm
DB_PASS="${SLURM_DB_PASS:-slurmpw}"

# The unprivileged user whose jobs need a slurm association. Defaults to
# whoever invoked sudo (the developer running the tests), falling back to root.
ASSOC_USER="${SLURM_ASSOC_USER:-${SUDO_USER:-root}}"

need_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        echo "[setup_slurm_local] re-executing under sudo..."
        exec sudo -E bash "$0" "$@"
    fi
}

install_pkgs() {
    if command -v sbatch >/dev/null 2>&1 \
        && command -v slurmdbd >/dev/null 2>&1 \
        && command -v mariadbd >/dev/null 2>&1; then
        echo "[setup_slurm_local] slurm + slurmdbd + mariadb already installed"
        return
    fi
    echo "[setup_slurm_local] installing slurm-wlm slurmdbd mariadb-server munge..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq slurm-wlm slurmdbd mariadb-server munge >/dev/null
}

setup_munge() {
    if [[ ! -f /etc/munge/munge.key ]]; then
        echo "[setup_slurm_local] creating munge key..."
        install -d -m 0700 -o munge -g munge /etc/munge
        dd if=/dev/urandom bs=1 count=1024 >/etc/munge/munge.key 2>/dev/null
        chown munge:munge /etc/munge/munge.key
        chmod 0400 /etc/munge/munge.key
    fi
    systemctl enable --now munge >/dev/null 2>&1 || systemctl restart munge
}

setup_mariadb() {
    echo "[setup_slurm_local] configuring MariaDB for slurmdbd..."
    systemctl enable --now mariadb >/dev/null 2>&1 || systemctl restart mariadb
    # Root authenticates via the unix socket on a stock Ubuntu install, so
    # ``mysql`` works without a password while we run as root.
    mysql <<SQL
CREATE DATABASE IF NOT EXISTS slurm_acct_db;
CREATE USER IF NOT EXISTS 'slurm'@'localhost' IDENTIFIED BY '${DB_PASS}';
GRANT ALL ON slurm_acct_db.* TO 'slurm'@'localhost';
FLUSH PRIVILEGES;
SQL
}

make_dirs() {
    install -d -m 0755 "$CONF_DIR"
    install -d -m 0755 -o slurm -g slurm "$STATE_DIR" "$SPOOL_DIR" "$LOG_DIR"
}

render_conf() {
    echo "[setup_slurm_local] rendering $CONF_PATH and $DBD_CONF_PATH ..."
    SLURM_STATE_DIR="$STATE_DIR" \
    SLURM_SPOOL_DIR="$SPOOL_DIR" \
    SLURM_RUN_DIR=/run \
    SLURM_LOG_DIR="$LOG_DIR" \
        bash "$HERE/render_slurm_conf.sh" "$CONF_PATH"
    chmod 0644 "$CONF_PATH"

    sed -e "s|@STORAGE_PASS@|${DB_PASS}|g" \
        -e "s|@LOG_DIR@|${LOG_DIR}|g" \
        -e "s|@RUN_DIR@|/run|g" \
        "$HERE/slurmdbd.conf.tmpl" > "$DBD_CONF_PATH"
    chown slurm:slurm "$DBD_CONF_PATH"
    chmod 0600 "$DBD_CONF_PATH"
    # On a native systemd host slurm manages cgroups through systemd, so no
    # IgnoreSystemd workaround (and thus no custom cgroup.conf) is needed here.
}

start_daemons() {
    systemctl enable --now slurmdbd >/dev/null 2>&1 || systemctl restart slurmdbd
    # Give slurmdbd a moment to come up before slurmctld registers with it.
    for _ in $(seq 1 20); do
        sacctmgr -i show cluster >/dev/null 2>&1 && break
        sleep 1
    done
    systemctl enable --now slurmctld slurmd >/dev/null 2>&1 || \
        systemctl restart slurmctld slurmd
    sleep 1
    scontrol update nodename="$(hostname -s)" state=RESUME 2>/dev/null || true
}

register_assoc() {
    echo "[setup_slurm_local] registering association for user '$ASSOC_USER'..."
    sacctmgr -i add account default Cluster=cmdq \
        Description="cmd_queue test account" 2>/dev/null || true
    sacctmgr -i add user "$ASSOC_USER" Account=default Cluster=cmdq 2>/dev/null || true
    # root submits during teardown/debugging too; harmless if it already exists.
    sacctmgr -i add user root Account=default Cluster=cmdq 2>/dev/null || true
}

stop_daemons() {
    systemctl stop slurmd slurmctld slurmdbd 2>/dev/null || true
}

case "$ACTION" in
    setup)
        need_root "$@"
        install_pkgs
        setup_munge
        setup_mariadb
        make_dirs
        render_conf
        start_daemons
        register_assoc
        echo
        echo "[setup_slurm_local] done. Cluster status:"
        sinfo || true
        echo
        echo "Next: python -m pytest tests/test_backend_execution.py -v -k slurm"
        ;;
    status)
        echo "== sinfo ==";    sinfo  || true
        echo "== squeue ==";   squeue || true
        echo "== sacctmgr =="; sacctmgr show assoc format=Cluster,Account,User 2>/dev/null || true
        ;;
    stop)
        need_root "$@"
        stop_daemons
        echo "[setup_slurm_local] slurm daemons stopped"
        ;;
    teardown)
        need_root "$@"
        stop_daemons
        rm -f "$CONF_PATH" "$DBD_CONF_PATH"
        echo "[setup_slurm_local] daemons stopped; $CONF_PATH and $DBD_CONF_PATH removed"
        echo "[setup_slurm_local] (packages + MariaDB data left in place)"
        ;;
    *)
        echo "usage: $0 [setup|status|stop|teardown]" >&2
        exit 2
        ;;
esac
