# Manually launch the null hisotrian agent. Useful for debugging as running this way will dump driver logging data directly to the console.
# The null historian is mainly for testing the performance of the base historian.
pushd agents/NullHistorian
AGENT_CONFIG=config python -m null_historian.agent
popd

