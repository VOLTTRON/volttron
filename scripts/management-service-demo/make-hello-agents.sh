WHEEL=$VOLTTRON_HOME/packaged/helloagent-0.1-py2-none-any.whl

volttron-pkg package ../../../Agents/HelloAgent/
volttron-pkg configure $WHEEL ./hello-config1

volttron-ctl stop --tag helloagent
volttron-ctl remove --tag helloagent
volttron-ctl install helloagent=$WHEEL


#volttron-pkg sign --creator /home/volttron/.volttron/packaged/multibuildingagent-0.1-py2-none-any.whl
#volttron-pkg sign --soi /home/volttron/.volttron/packaged/multibuildingagent-0.1-py2-none-any.whl 
#volttron-pkg sign --initiator /home/volttron/.volttron/packaged/multibuildingagent-0.1-py2-none-any.whl --config-file config/volttron-bsf.multinode.conf --contract Agents/ListenerAgent/execreqs.json

