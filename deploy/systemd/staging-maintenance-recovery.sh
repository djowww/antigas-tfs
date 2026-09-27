#!/bin/sh
# Independent ExecStopPost recovery for the approved isolated load-test window.
set -eu
systemctl stop imperium772-staging
systemctl set-property --runtime imperium772-staging MemoryMax=1G
systemctl start imperium772
