#!/bin/sh -e

if [ -z "$*" ]; then
	echo "Usage: $0 AGENT_DIRECTORY ..."
	exit 1
fi

SCRIPT="`readlink -f "$0"`"
SCRIPT_DIR="`dirname "$SCRIPT"`"
VOLTTRON_DIR="`dirname "$SCRIPT_DIR"`"
BASE_DIR="`dirname "$VOLTTRON_DIR"`"

while [ -n "$*" ]; do
	(cd "$BASE_DIR/Agents/$1" &&
		"$BASE_DIR/env/bin/python" setup.py bdist_egg --dist-dir "$BASE_DIR/Agents")
	shift
done

