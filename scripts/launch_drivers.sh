# Manually launch the master driver agent. Useful for debugging as running this way will dump driver logging data directly to the console.
pushd ../services/core/MasterDriverAgent
AGENT_CONFIG=master-driver.agent python -m master_driver.agent
popd

