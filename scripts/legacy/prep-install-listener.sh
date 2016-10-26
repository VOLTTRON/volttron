volttron-pkg package Agents/ListenerAgent/
volttron-pkg sign --creator /tmp/volttron_wheels/listeneragent-0.1-py2-none-any.whl
volttron-pkg sign --soi /tmp/volttron_wheels/listeneragent-0.1-py2-none-any.whl
volttron-pkg sign --initiator /tmp/volttron_wheels/listeneragent-0.1-py2-none-any.whl --contract Agents/ListenerAgent/execreqs.json --config-file Agents/ListenerAgent/config
