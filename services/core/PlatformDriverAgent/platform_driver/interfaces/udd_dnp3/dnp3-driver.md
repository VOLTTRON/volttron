
# DNP3 Driver


VOLTTRON's DNP3 driver enables the use of [DNP3 Distributed Network Protocol](https://en.wikipedia.org/wiki/DNP3)
communications, reading and writing points via a DNP3 Outstation.

In order to use a DNP3 driver to read and write point data, a server component (i.e., Outstation) must also
be configured and running. 


### Requirements

The DNP3 driver requires the [dnp3-python](https://github.com/VOLTTRON/dnp3-python) package, a wrapper on Pydnp3 package.
This package can be installed in an activated environment with:


    pip install dnp3-python


### Driver Configuration

There are arguments for the "driver_config" section of the DNP3 driver configuration file.

Here is a sample DNP3 driver configuration file:

```json
{
    "driver_config": {"master_ip": "0.0.0.0", "outstation_ip": "127.0.0.1",
        "master_id": 2, "outstation_id": 1,
        "port":  20000},
    "registry_config":"config://udd-Dnp3.csv",
        "driver_type": "udd_dnp3",
    "interval": 5,
    "timezone": "UTC",
    "campus": "campus-vm",
    "building": "building-vm",
    "unit": "Dnp3",
        "publish_depth_first_all": true,
    "heart_beat_point": "random_bool"
}
```
A sample data dictionary is available in ``services/core/PlatformDriverAgent/platform_driver/interfaces/udd_dnp3/examples/udd-Dnp3.config``.

### DNP3 Registry Configuration File

The driver's registry configuration file, a [CSV](https://en.wikipedia.org/wiki/Comma-separated_values) file,
specifies which DNP3 points the driver will read and/or write. Each row configures a single DNP3 point.

The following columns are required for each row:
- **Volttron Point Name** - The name used by the VOLTTRON platform and agents to refer to the point.
- **Group** - The point's DNP3 group number.
- **Variation** - THe permit negotiated exchange of data formatted, i.e., data type.
- **Index** - The point's index number within its DNP3 data type (which is derived from its DNP3 group number).
- **Scaling** - A factor by which to multiply point values.
- **Units** - Point value units.
- **Writable** - TRUE or FALSE, indicating whether the point can be written by the driver (FALSE = read-only).

Consult the **DNP3 data dictionary** for a point's Group and Index values. Point
definitions in the data dictionary are by agreement between the DNP3 Outstation and Master.
The VOLTTRON DNP3Agent loads the data dictionary of point definitions from the JSON file
at "point_definitions_path" in the DNP3Agent's config file.

A sample data dictionary is available in ``services/core/PlatformDriverAgent/platform_driver/interfaces/udd_dnp3/examples/udd-Dnp3.csv``.


Point definitions in the DNP3 driver's registry should look something like this:

| Point Name         | Volttron Point     | Group | Variation | Index | Scaling | Units |Writable| Notes|
|:-------------------|:-------------------|:------|:----------|:------|:--------|:------| :---  |:-----|
| AnalogInput_index0 | AnalogInput_index0 | 30    | 6         | 0     | 1       | NA    | FALSE |Double Analogue input without status|
| AnalogInput_index1 | AnalogInput_index1 | 30    | 6         | 1     | 1       | NA    | FALSE |Double Analogue input without status|
| BinaryInput_index0 | BinaryInput_index0 | 1     | 2         | 0     | 1       | NA    | FALSE |Double Analogue input without status|
| BinaryInput_index1 | BinaryInput_index1 | 1     | 2         | 1     | 1       | NA    | FALSE |Double Analogue input without status|

