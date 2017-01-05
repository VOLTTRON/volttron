#this shell script must be run from matlabgw (topmost) directory
#clean things up first
volttron-ctl stop --tag matlabgw &&\
volttron-ctl remove --tag matlabgw --force &&\
volttron-ctl list

#package it, then configure it to use the config file
volttron-pkg package ~/volttron/services/contrib/matlabgw &&\
volttron-pkg configure ~/.volttron/packaged/matlabgw-0.1.0-py2-none-any.whl ./matlabgw.config &&\
volttron-ctl install  ~/.volttron/packaged/matlabgw-0.1.0-py2-none-any.whl --tag matlabgw &&\
volttron-ctl enable --tag matlabgw &&\
volttron-ctl start  --tag matlabgw &&\
volttron-ctl list

