Deprecated
==========

-  Modify the driver.ini file

   -  Add your SMAP Key to the url
   -  Name your collection source
   -  Give your collection a uuid
   -  Enter your collection paths and metadata

-  If you are deploying the WeatherAgent update settings.py with your
   Weather Underground key
-  By default the Catalyst registers are setup to work with a 372 with
   the latest changes from TWT, if you have an older unit use the
   catalystreg.csv.371 file

Start the smap driver

::

    . bin/activate
    twistd -n smap driver.ini

With the platform already running:

-  Build agent eggs
-  Make egg executable
-  Install egg into bin (must not already exist there)
-  Load agent config file
-  Enable agent for autostart

.. raw:: html

   <!-- -->

::

    volttron/scripts/build-agent.sh ArchiverAgent
    chmod +x Agents/archiveragent-0.1-py2.7.egg
    bin/volttron-ctrl install-executable Agents/archiveragent-0.1-py2.7.egg
    bin/volttron-ctrl load-agent Agents/ArchiverAgent/archiver-deploy.service
    bin/volttron-ctrl enable-agent archiver-deploy.service
    bin/volttron-ctrl list-agents
    AGENT                    AUTOSTART  STATUS
    archiver-deploy.service   enabled

    volttron/scripts/build-agent.sh ActuatorAgent
    chmod +x Agents/actuatoragent-0.1-py2.7.egg 
    bin/volttron-ctrl install-executable Agents/actuatoragent-0.1-py2.7.egg
    bin/volttron-ctrl load-agent Agents/ActuatorAgent/actuator-deploy.service
    bin/volttron-ctrl enable-agent actuator-deploy.service

Do the same things for WeatherAgent if you plan to deploy it.

Control Application Example Install one executable but multiple launch
configuration files. Each instance of this agent will work with a
different RTU.

::

    volttron/scripts/build-agent.sh SMDSAgent
    chmod +x Agents/SMDSagent-0.1-py2.7.egg
    bin/volttron-ctrl install-executable Agents/SMDSagent-0.1-py2.7.egg
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-lbnl1.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-lbnl2.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-lbnl3.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-lbnl4.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-lbnl5.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-lbnl6.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-lbnl7.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-twt1.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-twt2.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-twt3.agent
    bin/volttron-ctrl load-agent Agents/SMDSAgent/smds-twt4.agent

    bin/volttron-ctrl enable-agent smds-lbnl1.agent
    bin/volttron-ctrl enable-agent smds-lbnl2.agent
    bin/volttron-ctrl enable-agent smds-lbnl3.agent
    bin/volttron-ctrl enable-agent smds-lbnl4.agent
    bin/volttron-ctrl enable-agent smds-lbnl5.agent
    bin/volttron-ctrl enable-agent smds-lbnl6.agent
    bin/volttron-ctrl enable-agent smds-lbnl7.agent
    bin/volttron-ctrl enable-agent smds-twt1.agent
    bin/volttron-ctrl enable-agent smds-twt2.agent
    bin/volttron-ctrl enable-agent smds-twt3.agent
    bin/volttron-ctrl enable-agent smds-twt4.agent

Restart platform and agents you have enable for autostart should start
up.
