. demo-vars.sh

echo "(Re)creating Platform Directories:"
echo "$V1_HOME, $V2_HOME, $V3_HOME"
if [ -d "$V1_HOME" ]; then
  rm -rf $V1_HOME
fi

if [ -d "$V2_HOME" ]; then
  rm -rf $V2_HOME
fi

if [ -d "$V3_HOME" ]; then
  rm -rf $V3_HOME
fi

# We add the curve.key to not include encryption
# on tcp communication.
mkdir $V1_HOME
touch $V1_HOME/curve.key
mkdir $V2_HOME
touch $V2_HOME/curve.key
mkdir $V3_HOME
touch $V3_HOME/curve.key
