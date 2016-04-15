VOLTTRON Central is a platform management web application that allows
platforms to communicate and to be managed from a centralized server.
This agent alleviates the need to ssh into independent nodes in order to
manage them. The demo will start up 3 different instances of VOLTTRON
with 3 historians and different agents on each host. The following
entries will help to navigate around the VOLTTRON Central interface.

-  `Running the Demo <#running-the-demo>`__
-  `Stopping the Demo <#stopping-the-demo>`__
-  `The Login <#login>`__
-  `Logging Out <#logout>`__
-  `Platforms Screen <#platforms-screen>`__
-  `Register new Platform <#register-new-platform>`__
-  `Deregister Platform <#deregister-platform>`__
-  `Platform View <#platform-view>`__
-  `Start and Stop Agents <#start-and-stop-agents>`__
-  `Add Chart <#add-chart>`__
-  `Edit Chart <#edit-chart>`__

Running the Demo
----------------

After `building VOLTTRON <Building-VOLTTRON>`__, open a shell with the
current directory the root of the volttron repository. Activate the
shell

::

    . env/bin/activate

execute the script

::

    ./volttron/scripts/management-service-demo/run-demo

Upon completion a browser window (opened to http://localhost:8080/)
should be opened with a login prompt and the shell should look like the
following image.

|Run VC Demo|

#. Log into the front page using credentials admin/admin.
#. From the console window copy the first platform address from the
   shell.
#. In the upper right of the browser window, click Platforms, then click
   Register Platform.
#. Type 'Platform 1' in the name parameter and paste the first platforms
   ipc address that you copied from step 2.

-  The Platform 1 should show up in the list of platforms on this page.

#. Repeat step 4 for the other 2 platforms.

Stopping the Demo
~~~~~~~~~~~~~~~~~

Once you have completed your walk through of the different elements of
the VOLTTRON Central demo you can stop the demos by executing

::

    ./scripts/management-service-demo/stop-platforms.sh

Once the demos is complete you may wish to see the `VOLTTRON
Central <VOLTTRON-Central>`__ page for more details on how to configure
the agent for your specific use case.

Login
~~~~~

| To login to the Management Platform, navigate in a browser to
localhost:8080, and enter the username and password on the login screen.
| |Login Screen|

Logout
~~~~~~

| To logout of the Management Platform, click the link at the top right
of the screen.
| |Logout Button|

Platforms Screen
----------------

| This screen lists the registered VOLTTRON Platforms, and allows new
platforms to be registered by clicking the button in the top right
corner of the screen. This includes the Platform UID as well as the
number of agents running, stopped and installed on each platform.
| |Platforms|

Register new Platform
~~~~~~~~~~~~~~~~~~~~~

| To register a new VOLTTRON Platform, click the Button in the corner of
the screen. You will need to provide a name and the IP address of the
VOLTTRON Platform.
| |Register Platform Information|

Deregister Platform
~~~~~~~~~~~~~~~~~~~

To deregister a VOLTTRON Platform, click on the ‘X’ at the far right of
the platform display.

Platform View
-------------

| Use the Platform View to manage a specific VOLTTRON Platform. This
includes installing agents, start/stop agents, and configuring charts.
| |Platform Screen|

Install Agent
~~~~~~~~~~~~~

To install a new agent, all you need is the agent’s wheel file. Click on
the button To upload the wheel file used to install the agent.

Start and Stop Agents
~~~~~~~~~~~~~~~~~~~~~

| To Start or Stop an Agent, click on the button as shown in the figure.
If the agent is running, its PID will be displayed.
| |Start Agent Button|

Add Chart
~~~~~~~~~

| To add a chart, click the Add Chart button. You will need to provide
the published topic the chart pulls data from. You may also select
refresh interval and chart type as well as pin the chart to the
dashboard.
| |Add Chart Screen|

Edit Chart
~~~~~~~~~~

| To edit a chart, click the edit chart button. You will get a popup
window of settings for the chart, as shown in the figure. To pin the
chart to the dashboard select the checkbox.
| |Edit Chart Screen|

.. |Run VC Demo| image:: files/vc-run-demo.png
.. |Login Screen| image:: files/login-screen.png
.. |Logout Button| image:: files/logout-button.png
.. |Platforms| image:: files/platforms.png
.. |Register Platform Information| image:: files/register-new-platform.png
.. |Platform Screen| image:: files/platform-default.png
.. |Start Agent Button| image:: files/start-agent.png
.. |Add Chart Screen| image:: files/add-chart.png
.. |Edit Chart Screen| image:: files/edit-chart.png
