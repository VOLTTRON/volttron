# IEEE2030_5 Agent
Agent that handles IEEE 2030.5 communication.
IEEE2030_5Agent uses the VOLTTRON web service to communicate with IEEE 2030.5  end devices.
End device configuration is outlined in the agent config file.

IEEE 2030.5 data is exposed via get_point(), get_points() and set_point() calls.
A IEEE 2030.5 device driver (IEEE2030_5.py under MasterDriverAgent) can be configured,
which gets and sets data by sending RPCs to this agent.

For further information about this subsystem, please see the VOLTTRON
IEEE 2030.5 DER Support specification, which is located in VOLTTRON readthedocs
under specifications/IEEE2030_5_agent.html.

## Configuration

``` {.python}
{
    "devices": [
                    {
                        "sfdi": "097935300833",
                        "lfdi": "247bd68e3378fe57ba604e3c8bdf9e3f78a3d743",
                        "load_shed_device_category": "0200",
                        "pin_code": "130178"
                    },
                    {
                        "sfdi": "111576577659",
                        "lfdi": "2990c58a59935a7d5838c952b1a453c967341a07",
                        "load_shed_device_category": "0200",
                        "pin_code": "130178"
                    }
               ],
    "IEEE2030_5_server_sfdi": "413707194130",
    "IEEE2030_5_server_lfdi": "29834592834729384728374562039847629",
    "load_shed_device_category": "0020",
    "timezone": "America/Los_Angeles"
}
```
