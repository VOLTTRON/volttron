mkdir -p /sys/fs/cgroup
mount -t tmpfs cgroup /sys/fs/cgroup
mkdir -p /sys/fs/cgroup/{cpu,memory}
mount -t cgroup -o cpu cgroup-cpu /sys/fs/cgroup/cpu
mount -t cgroup -o memory cgroup-memory /sys/fs/cgroup/memory
chmod a+rw /sys/fs/cgroup
chmod -R a+rw /sys/fs/cgroup

