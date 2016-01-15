# Manually launch the listener agent. Useful for debugging as running this way will dump driver logging data directly to the console.
pushd ../examples/ListenerAgent
AGENT_CONFIG=config python -m listener.agent
popd

