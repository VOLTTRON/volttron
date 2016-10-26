. vars.sh

echo "Shutting down platform 1"
VOLTTRON_HOME=$V1_HOME volttron-ctl shutdown --platform&
echo "Shutting down platform 2"
VOLTTRON_HOME=$V2_HOME volttron-ctl shutdown --platform&



