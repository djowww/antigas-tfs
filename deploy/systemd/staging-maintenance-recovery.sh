#!/bin/sh
# Independent ExecStopPost recovery for the approved isolated load-test window.
# Attempt every recovery step even if stopping staging or restoring its limit fails.
set -u
failed=0
systemctl stop imperium772-staging || failed=1
systemctl set-property --runtime imperium772-staging MemoryMax=1G || failed=1
systemctl start imperium772 || failed=1
exit "$failed"
