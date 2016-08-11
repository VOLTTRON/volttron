.. _Develop-Driver-Agent:

Driver Development
==================

Introduction
------------

All Voltton drivers are implemented through the :doc:`Master Driver
Agent <../../core_services/drivers/Driver-Configuration>` and are technically sub-agents running in
the same process as the :doc:`Master Driver
Agent <../../core_services/drivers/Driver-Configuration>`.
Each of these driver sub-agents is responsible for creating an interface
to a single device. Creating that interface is facilitated by an
instance of an interface class. Currently there are two interface
classes included: `Modbus <Modbus-Driver>`__ and
`BACnet <BACnet-Driver>`__.

Existing Drivers
----------------

In the directory for the Master Driver Agent you'll see a directory
called interfaces:

::

    ├── master_driver
    │   ├── agent.py
    │   ├── driver.py
    │   ├── __init__.py
    │   ├── interfaces
    │   │   ├── __init__.py
    │   │   ├── bacnet.py
    │   │   └── modbus.py
    │   └── socket_lock.py
    ├── master-driver.agent
    └── setup.py

The files bacnet.py and modbus.py implement the interface class for each
respective protocol. (The BACnet interface is mostly just a pass-though
to the :ref:`BACnet Proxy Agent <BACnet-Proxy-Agent>`, but the Modbus
interface is self contained.)

Looking at those two files is a good introduction into how they work.

The file name is used when configuring a driver to determine which
interface to use. The name of the interface class in the file must be
called Interface.

Interface Basics
----------------

A complete interface consists of two parts: One or more register classes
and the interface class.

Register Class
~~~~~~~~~~~~~~

The Base Interface class uses a Register class to describe the registers
of a device to the driver sub-agent. This class is commonly sub-classed
to store protocol specific information for the interface class to use.
For example, the BACnet interface uses a sub-classed base register to
store the instance number, object type, and property name of the point
on the device represented by the register class. The Modbus interface
uses several different Register classes to deal with the different types
of registers on Modbus devices and their different needs.

The register class contains the following attributes:

-  **read\_only** - True or False
-  **register\_type** - "bit" or "byte", used by the driver sub-agent to
   help deduce some meta data about the point.
-  **point\_name** - Name of the point on the device. Used by the base
   interface for reference.
-  **units** - units of the value, meta data for the driver
-  **description** - meta data for the driver
-  **python\_type** - python type of the point, used to produce meta
   data. This must be set explicitly otherwise it default to int.

Here is an example of a Registry Class for the BACnet driver:

::

    class Register(BaseRegister):
        def __init__(self, instance_number, object_type, property_name, read_only, pointName, units, description = ''):
            super(Register, self).__init__("byte", read_only, pointName, units, description = '')
            self.instance_number = int(instance_number)
            self.object_type = object_type
            self.property = property_name

Note that this implementation is incomplete. It does not properly set
the register\_type or python\_type.

Interface Class
~~~~~~~~~~~~~~~

The Interface Class is what is instantiated by the driver sub-agent to
do it's work.

configure(self, config\_dict, registry\_config\_str)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method must be implemented by an Interface implementation.

-  **config\_dict** is a dictionary of key values pairs from the
   configuration file's "driver\_config" section.
-  **registry\_config\_str** is the contents of the "registry\_config"
   entry in the driver configuration file. It is up to the Interface
   class to parse this file according to the needs of the driver.

Here is an example taken from the :ref:`BACnet <BACnet-driver-config>` driver:

::

    def configure(self, config_dict, registry_config_str):
        self.parse_config(registry_config_str) #Parse the configuration string. 
        self.target_address = config_dict["device_address"]
        self.proxy_address = config_dict.get("proxy_address", "platform.bacnet_proxy")
        self.ping_target(self.target_address) #Establish routing to the device if needed.

And here is the parse\_config method (See :ref:`BACnet Registry
Configuration <BACnet-Registry-Configuration-File>`:

::

    def parse_config(self, config_string):
        if config_string is None:
            return
        
        f = StringIO(config_string) #Python's CSV file parser wants a file like object.
        
        configDict = DictReader(f) #Parse the CVS file contents.
        
        for regDef in configDict:
            #Skip lines that have no address yet.
            if not regDef['Point Name']:
                continue
            
            io_type = regDef['BACnet Object Type']
            read_only = regDef['Writable'].lower() != 'true'
            point_name = regDef['Volttron Point Name']        
            index = int(regDef['Index'])        
            description = regDef['Notes']                 
            units = regDef['Units']       
            property_name = regDef['Property']       
                        
            register = Register(index, 
                                io_type, 
                                property_name, 
                                read_only, 
                                point_name,
                                units, 
                                description = description)
                
            self.insert_register(register)

Once a register is created it must be added with the insert\_register
method.

get\_point(self, point\_name)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method must be implemented by an Interface implementation.

Gets the value of a point from a device and returns it.

Here is a simple example from the BACnet driver. In this case it only
has to pass the work on to the BACnet Proxy Agent for handling.

::

    def get_point(self, point_name): 
        register = self.get_register_by_name(point_name)   
        point_map = {point_name:[register.object_type, 
                                 register.instance_number, 
                                 register.property]}
        result = self.vip.rpc.call(self.proxy_address, 'read_properties', 
                                       self.target_address, point_map).get()
        return result[point_name]

Failure should be indicated by a useful exception being raised. (In this
case the we just leave the Exception raised by the BACnet proxy
un-handled. This could be improved with better handling when register
that does not exist is requested.)

The Register instance for the point can be retrieved with
self.get\_register\_by\_name(point\_name)

set\_point(self, point\_name, value)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method must be implemented by an Interface implementation.

Sets the value of a point on a device and ideally returns the actual
value set if different.

Here is a simple example from the BACnet driver. In this case it only
has to pass the work on to the BACnet Proxy Agent for handling.

::

    def set_point(self, point_name, value):    
        register = self.get_register_by_name(point_name)  
        if register.read_only:
            raise  IOError("Trying to write to a point configured read only: "+point_name)
        args = [self.target_address, value,
                register.object_type, 
                register.instance_number, 
                register.property]
        result = self.vip.rpc.call(self.proxy_address, 'write_property', *args).get()
        return result

Failure to raise a useful exception being raised. (In this case the we
just leave the Exception raised by the BACnet proxy un-handled unless
the point is read only.)

scrape\_all(self)
^^^^^^^^^^^^^^^^^

This method must be implemented by an Interface implementation.

This must return a dictionary mapping point names to values for ALL
registers.

Here is a simple example from the BACnet driver. In this case it only
has to pass the work on to the BACnet Proxy Agent for handling.

::

    def scrape_all(self):
        point_map = {}
        read_registers = self.get_registers_by_type("byte", True)
        write_registers = self.get_registers_by_type("byte", False) 
        for register in read_registers + write_registers:             
            point_map[register.point_name] = [register.object_type, 
                                              register.instance_number, 
                                              register.property]
        
        result = self.vip.rpc.call(self.proxy_address, 'read_properties', 
                                       self.target_address, point_map).get()
        return result

self.get\_registers\_by\_type allows you to get lists of registers by
their type and if they are read only. (As BACnet currently only uses
"byte", "bit" is ignored.) As the procedure for handling all the
different types in BACnet is the same we can bundle them all up into a
single request from the proxy.

In the Modbus protocol the distinction is important and so each category
must be handled differently.
