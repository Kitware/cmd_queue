# Single-node Slurm cluster in a container, for exercising cmd_queue's slurm
# backend end-to-end (sbatch/squeue/scontrol) without touching the host.
#
# Build + run via ``dev/slurm/run_slurm_tests_in_docker.sh`` (it mounts the
# repo and runs pytest), or by hand:
#
#   docker build -f dev/slurm/Dockerfile -t cmd_queue-slurm dev/slurm
#   docker run --rm -it --privileged -v "$PWD:/io" cmd_queue-slurm \
#       bash -lc 'cd /io && pip install -e . && pytest tests/test_backend_execution.py -k slurm'
#
# --privileged is required so the entrypoint can delegate cgroup v2
# controllers for slurmd (see cgroup_prep.sh).
FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

# slurm-wlm pulls in slurmctld/slurmd/sbatch; slurmdbd + mariadb-server back
# the accounting database (required since accounting_storage/none was
# deprecated in 23.11); munge is slurm's auth layer.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        slurm-wlm \
        slurmdbd \
        mariadb-server \
        munge \
        python3 \
        python3-pip \
        python3-venv \
        git \
        ca-certificates \
        procps \
    && rm -rf /var/lib/apt/lists/*

# Spool/state/log dirs the daemons need, owned by the distro 'slurm' user.
RUN mkdir -p /var/spool/slurm/ctld /var/spool/slurm/d /var/log/slurm \
    && chown -R slurm:slurm /var/spool/slurm /var/log/slurm

COPY slurm.conf.tmpl slurmdbd.conf.tmpl render_slurm_conf.sh cgroup_prep.sh entrypoint.sh \
     /opt/slurm-setup/
RUN chmod +x /opt/slurm-setup/render_slurm_conf.sh \
             /opt/slurm-setup/cgroup_prep.sh \
             /opt/slurm-setup/entrypoint.sh

# The entrypoint boots munge + slurmctld + slurmd, waits for the node to go
# IDLE, then exec's whatever command you pass (default: an interactive shell).
ENTRYPOINT ["/opt/slurm-setup/entrypoint.sh"]
CMD ["bash"]
