#ifndef FUNCTION_H
#define FUNCTION_H

#include <iostream>
#include <fstream>
#include <string>

namespace modbus_device
{

  class Function
  {
    public:
	    Function();

        const std::string& Name();
        void  SetName( const std::string& Name );

        const std::string& Description();
        void  SetDescription( const std::string& Description );

        const std::string& Addresses();
        void  SetAddresses( const std::string& Addresses );

        const std::string& Length();
        void  SetLength( const std::string& Length );

        int Count();
        void  SetCount( const int& Count );

        const std::string& Format();
        void  SetFormat( const std::string& Format );

        const std::string& BlockLabel();
        void  SetBlockLabel( const std::string& BlockLabel );

        float Multiplier();
        void  SetMultiplier( const float& Multiplier );

        const std::string& Units();
        void  SetUnits( const std::string& Units );

        const std::string& ReadFunctionCode();
        void  SetReadFunctionCode( const std::string& ReadFunctionCode );

        const std::string& WriteFunctionCode();
        void  SetWriteFunctionCode( const std::string& WriteFunctionCode );

        void WriteHeader(std::ofstream& fout);
        void WriteSource(std::string deviceName, std::ofstream& fout);
        
    private:
        std::string name;
		std::string description;
		std::string addresses;
		std::string length;
		int         count;
		std::string format;
		std::string block_label;
		float       multiplier;
		std::string units;
		std::string read_function_code;
		std::string write_function_code;
  };

}

#endif
