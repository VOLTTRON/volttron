# bring in the vars that are to be available for this script
. demo-vars.sh

echo "Starting platform 1"
VOLTTRON_HOME=$V1_HOME volttron -vv&
echo "Starting platform 2"
VOLTTRON_HOME=$V2_HOME volttron -vv&
echo "Starting platform 3"
VOLTTRON_HOME=$V3_HOME volttron -vv&

