
Deployment Recommendations
==========================

Ensuring the safe operation of devices working with VOLTTRON is
essential. This page will discuss recommendations/experiences for doing
deployments to meet these needs.

In a previous deployment, VOLTTRON worked with a facilities manager to
create virtual points which the platform would control:

-  VolttronEnabled
-  VolttronHeartbeat
-  VoltronOverride
-  VolttronCoolingSetPoint

When VOLTTRON is active it sets the VolttronEnabled flag. It also
twiddles the VolttronHeartbeat point every minute. While the Enabled
flag is set and the Heartbeat is active, the controller will use
VOLTTRON specific points instead of base points (VolttronCoolingSetPoint
instead of CoolingSetPoint).

If VolttronOveride is set then the controller ignores the VOLTTRON
points and reverts to normal operation. Likewise, if the Heartbeat point
is not being actively set by the platform or if VolttronEnabled is
false, then the controller reverts to normal control.

If VolttronEnabled and (active Heartbeat) and not (VolttronOverride)
then use Volttron virtual points
