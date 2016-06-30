rticonnextdds-connector: Python
========

### Installation and Platform support
Check [here](https://github.com/rticommunity/rticonnextdds-connector#getting-started-with-python) and [here](https://github.com/rticommunity/rticonnextdds-connector#platform-support).
If you still have trouble write on the [RTI Community Forum](https://community.rti.com/forums/technical-questions)

### Available examples
In this directory you can find 1 set of examples

 * **simple**: shows how to write samples and how to read/take

### API Overview:
#### require the connector library
If you want to use the `rticonnextdds_connector` you have to import it:

```py
import rticonnextdds_connector as rti
```

#### instantiate a new connector
To create a new connector you have to pass an xml file and a configuration name. For more information on
the XML format check the [XML App Creation guide](https://community.rti.com/rti-doc/510/ndds.5.1.0/doc/pdf/RTI_CoreLibrariesAndUtilities_XML_AppCreation_GettingStarted.pdf) or
have a look to the [ShapeExample.xml](ShapeExample.xml) file included in this directory.  

```py
connector = rti.Connector("MyParticipantLibrary::Zero","./ShapeExample.xml");
```

#### write a sample
To write a sample first we have to get a reference to the output port:

```py
output = connector.getOutput("MyPublisher::MySquareWriter")
```

then we have to set the instance's fields:

```py
output.instance.setNumber("x", 1);
output.instance.setNumber("y", 2);
output.instance.setNumber("shapesize", 30);
output.instance.setString("color", "BLUE");
```

and then we can write:

```py
output.write();
```

#### setting the instance's fields:
The content of an instance can be set using a dictionary that matches the original type, or field by field:

* **Using a dictionary**:

```py
#assuming that sample is a dictionary containing
#an object of the same type of the output.instance:

output.instance.setDictionary(sample);
```

 * **Field by field**:

```py
output.instance.setNumber("y", 2);
```

The APIs to do that are only 3: `setNumber(fieldName, number);` `setBoolean(fieldName, boolean);` and `setString(fieldName, string);`.

Nested fields can be accessed with the dot notation: `"x.y.z"`, and array with square brakets: `"x.y[1].z"`. For more info on how to access
fields, check Section 6.4 'Data Access API' of the
[RTI Prototyper Getting Started Guide](https://community.rti.com/rti-doc/510/ndds.5.1.0/doc/pdf/RTI_CoreLibrariesAndUtilities_Prototyper_GettingStarted.pdf)


#### reading/taking data
To read/take samples first we have to get a reference to the input port:

```py
input = connector.getInput("MySubscriber::MySquareReader");
```

then we can call the `read()` or `take()` API:

```py
input.read();
```

 or

```pu
 input.take();
```

The read/take operation can return multiple samples. So we have to iterate on an array:

```py
    input.take();
    numOfSamples = input.samples.getLength();
    for j in range (1, numOfSamples+1):
        if input.infos.isValid(j):
            x = input.samples.getNumber(j, "x");
            y = input.samples.getNumber(j, "y");
            size = input.samples.getNumber(j, "shapesize");
            color = input.samples.getString(j, "color");
            toPrint = "Received x: " + repr(x) + " y: " + repr(y) + " size: " + repr(size) + " color: " + repr(color);
            print(toPrint);
}
```

#### accessing samples fields after a read/take
A `read()` or `take()` operation can return multiple samples. They are stored in an array. Every time you try to access a specific sample you have to specify an index (j in the example below).

You can access the date by getting a copy in a dictionary object or you can access each field individually:

 * **Using a dictionary**:

```py
 numOfSamples = input.samples.getLength();
 for j in range (1, numOfSamples+1):
     if input.infos.isValid(j):
         sample = input.samples.getDictionary(j);
         #print the whole sample
         print(sample);
         #or print a single element
         print(sample['x']);
 }
```

 * **Field by field**:

```py
 numOfSamples = input.samples.getLength();
 for j in range (1, numOfSamples+1):
     if input.infos.isValid(j):
         x = input.samples.getNumber(j, "x");
         y = input.samples.getNumber(j, "y");
         size = input.samples.getNumber(j, "shapesize");
         color = input.samples.getString(j, "color");
         toPrint = "Received x: " + repr(x) + " y: " + repr(y) + " size: " + repr(size) + " color: " + repr(color);
         print(toPrint);
 }
```

The APIs to do that are only 3: `getNumber(indexm fieldName);` `getBoolean(index, fieldName);` and `getString(index, fieldName);`.
