. demo-vars.sh

echo "(Re)creating Platform Directories:"
echo "$V1_HOME, $V2_HOME, $V3_HOME"
if [ -d "$V1_HOME" ]; then
  rm $V1_HOME -rf
fi

if [ -d "$V2_HOME" ]; then
  rm $V2_HOME -rf
fi

if [ -d "$V3_HOME" ]; then
  rm $V3_HOME -rf
fi

mkdir $V1_HOME
mkdir $V2_HOME
mkdir $V3_HOME
