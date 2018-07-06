/**
 * This is a parser and code generator for the Modbus Description Language (MDL).
 * The code generator creates a C++ class for accessing a Modbus device that is
 * described in the MDL. This C++ class acts as a wrapper around libmodbus calls
 * for fetching and getting register and coil values.
 */

#ifdef HAVE_CONFIG_H
#include <config.h>
#endif

#include <iostream>
#include <string>
#include "device.h"

using namespace std;
using namespace modbus_device;

int main(int argc, char *argv[])
{
    Device device;

    std::string filepath;
    if(argc == 2 )
         filepath = argv[1]; 
    else
    {
        cout<< "Usage: "<<argv[0] << " xml-file" <<endl;
        return 1;
    }

    cout << "Reading MDL XML file " << filepath << endl;
    device.ReadXMLFile(filepath);
    cout << "Done"<<endl<<endl;       

    cout << "Writing header file"<< endl;
    device.WriteHeader();
    

    cout << "Writing source file"<< endl;
    device.WriteSource();

    cout << "All done"<< endl;
    return 0;
}
