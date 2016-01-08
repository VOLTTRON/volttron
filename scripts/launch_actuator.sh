# Manually launch the actuator agent. Useful for debugging as running this way will dump driver logging data directly to the console.
pushd ../services/core/ActuatorAgent
AGENT_CONFIG=actuator-deploy.service python -m actuator.agent
popd

