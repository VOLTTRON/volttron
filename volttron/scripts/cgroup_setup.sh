#!/bin/sh

set -e

CGROUP=/sys/fs/cgroup

if ! mountpoint -q $CGROUP; then
 mkdir -p $CGROUP
 mount -t tmpfs cgroup $CGROUP
fi

if ! mountpoint -q $CGROUP/cpu; then
 mkdir $CGROUP/cpu
 mount -t cgroup -o cpu cgroup-cpu $CGROUP/cpu
fi

if ! mountpoint -q $CGROUP/memory; then
 mkdir $CGROUP/memory
 mount -t cgroup -o memory cgroup-memory $CGROUP/memory
fi
