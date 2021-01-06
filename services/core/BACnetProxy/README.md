# BACnet Proxy Agent

Communication with BACnet device on a network happens via a single virtual BACnet device. In VOLTTRON driver framework,
we use a separate agent specifically for communicating with BACnet devices and managing the virtual BACnet device.

## Dependencies
1. The BACnet Proxy agent requires the BACPypes package. This package can be installed in an activated environment with:
    ```
    pip install bacpypes
    ```
2. Current versions of VOLTTRON support only BACPypes version 0.16.7

## Agent Configuration

```
    {
        "device_address": "10.0.2.15",
        "max_apdu_length": 1024,
        "object_id": 599,
        "object_name": "Volttron BACnet driver",
        "vendor_id": 15,
        "segmentation_supported": "segmentedBoth"
    }
```
1. device_address - Address bound to the network port over which BACnet communication will happen on the computer
running VOLTTRON. This is NOT the address of any target device.
2. object_id - ID of the Device object of the virtual BACnet device. Defaults to 599. Only needs to be changed if there
is a conflicting BACnet device ID on your network.
3. max_apdu_length - Maximum size message the device can handle
4. object_name - Name of the object. Defaults to “Volttron BACnet driver”. (Optional)
5. vendor_id - Vendor ID of the virtual BACnet device. Defaults to 15. (Optional)
6. segmentation_supported -  Segmentation allows larger messages to be broken up into segments and spliced back together.
Possible setting are “segmentedBoth” (default), “segmentedTransmit”, “segmentedReceive”, or “noSegmentation” (Optional)
