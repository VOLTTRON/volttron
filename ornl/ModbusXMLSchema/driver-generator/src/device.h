#ifndef DEVICE_H
#define DEVICE_H

#include <libxml++/libxml++.h>

#include "function.h"
#include <iostream>
#include <string>
#include <vector>

namespace modbus_device
{

  class Device
  {
    public:
	    Device();

        const std::string& Name();
        void  SetName( const std::string& Name );

        const std::string& Description();
        void  SetDescription( const std::string& Description );

        int FunctionCount();

        void WriteHeader();
        void WriteSource();

        void AddFunction(const Function* func);

        void ReadXMLFile(const std::string& filename);
    
    protected:
        void readFunction(const xmlpp::Node* node);
        std::string getNodeValue(const xmlpp::Node* node);

        std::string name;
        std::string description;
        std::vector <Function> functions;
  };

}


#endif
