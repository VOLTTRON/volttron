#!/bin/bash
# Script for recompiling the React UI for Voltron
#
# Needs to run on the host, as volttron.

  pushd /home/volttron/volttron/services/core/VolttronCentral
  git pull 
  nodejs node_modules/gulp/bin/gulp.js & 
  FOO_PID=$!
  volttron-ctl stop --tag vc
  volttron-ctl remove --tag vc 
  sleep 10 &&  kill -TERM $FOO_PID
  volttron-pkg package . && volttron-pkg configure /home/volttron/.volttron/packaged/volttroncentralagent-3.5.5-py2-none-any.whl config 
  volttron-ctl install /home/volttron/.volttron/packaged/volttroncentralagent-3.5.5-py2-none-any.whl --tag vc
  volttron-ctl start --tag vc
  popd
