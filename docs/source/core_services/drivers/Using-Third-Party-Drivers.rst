.. _Using-Third-Party-Drivers:

=========================
Using Third Party Drivers
=========================

In some cases you will need to use a driver provided by a third-party to interact with a device.
While the interface file can be copied into ``services/core/MasterDriverAgent/master_driver/interfaces``
this does not work well with third-party code that is under source control.

The recommended method is to create a symbolic link to the interface file in
``services/core/MasterDriverAgent/master_driver/interfaces``. This will work in both
a development environment and in production. When packing the agent for installation
a copy of the linked file will be put in the resulting wheel file.

::

    #A copy of the interface file lives in ~/my_driver/my_driver.py
    #Create the link
    ln -s ~/my_driver/my_driver.py services/core/MasterDriverAgent/master_driver/interfaces/my_driver.py

    #remove the link
    rm services/core/MasterDriverAgent/master_driver/interfaces/my_driver.py
