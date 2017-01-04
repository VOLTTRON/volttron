#include <algorithm>
#include "function.h"

using namespace modbus_device;
using namespace std;

Function::Function()
{
    count = 0;
    multiplier = 0;
}

const string& Function::Name()
{
    return name;
}
        
void Function::SetName( const string& Name )
{
    name = Name;
}

const string& Function::Description()
{
    return description;
}

void Function::SetDescription( const string& Description )
{
    description = Description;
}

const string& Function::Addresses()
{
    return addresses;
}
void Function::SetAddresses( const string& Addresses )
{
    addresses = Addresses;
}

const string& Function::Length()
{
    return length;
}

void Function::SetLength( const string& Length )
{
    length = Length;
}

int Function::Count()
{
    return count;
}

void Function::SetCount( const int& Count )
{
    count = count;
}

const string& Function::Format()
{
    return format;
}

void Function::SetFormat( const string& Format )
{
    format = Format;
}

const string& Function::BlockLabel()
{
    return block_label;
}

void Function::SetBlockLabel( const string& BlockLabel )
{
    block_label = BlockLabel;
}

float Function::Multiplier()
{
    return multiplier;
}

void Function::SetMultiplier( const float& Multiplier )
{
    multiplier = Multiplier;
}

const string& Function::Units()
{
    return units;
}

void Function::SetUnits( const string& Units )
{
    units = Units;
}

const string& Function::ReadFunctionCode()
{
    return read_function_code;
}

void Function::SetReadFunctionCode( const string& ReadFunctionCode )
{
    read_function_code = ReadFunctionCode;
}

const string& Function::WriteFunctionCode()
{
    return write_function_code;
}

void Function::SetWriteFunctionCode( const string& WriteFunctionCode )
{
    write_function_code = WriteFunctionCode;
}

void Function::WriteHeader(ofstream &fout)
{
    static const char* spc = "   ";

    fout << endl;
    fout << spc << "/* " << this->Description() << " */" << endl;

    string dataType = this->Format();
    std::transform( dataType.begin(), dataType.end(), dataType.begin(), ::tolower );

    if (this->Multiplier() != 0 || !(this->ReadFunctionCode().empty()) )
        fout << spc << dataType << " " << this->Name()<< "();" << endl;

    if ( !(this->WriteFunctionCode().empty()) )
        fout << spc << "void set_" << this->Name() << "(" << dataType << " arg);" << endl;
}

void Function::WriteSource(string deviceName, ofstream& fout)
{
    static const char* spc = "   ";

    fout << endl;
    fout << "/* " << this->Description() << " */" << endl;

    string dataType = this->Format();
    std::transform( dataType.begin(), dataType.end(), dataType.begin(), ::tolower );

    if (this->Multiplier() != 0 || !(this->ReadFunctionCode().empty()) )
    {
    	fout << dataType << " " << deviceName << "::" << this->Name() << "() {" << endl;
		for (int i = 1; i <= this->Count() ; i++)
		{
			fout << spc << "uint16_t& r" << i << " = r[" << (i-1) << "];" << endl;
		}
		fout << spc << dataType << " arg;" << endl;
		fout << spc << "errno = 0;" << endl;
		fout << spc << "if (modbus_read_registers(md," << this->Addresses() << "," << this->Count() << ",r) == -1) {" << endl;
		fout << spc << spc << "throw modbus_exception(errno,modbus_strerror(errno));" << endl;
		fout << spc << "}" << endl;

        // echo read_function_code if present, or use multiplier to generate conversion
        if( !(this->ReadFunctionCode().empty()) )
        	fout << spc << this->ReadFunctionCode() << endl;
        else 
        {
            // output similar to:  arg = (float)(r1)/10.0f;
            fout << spc << "arg = (float)(r1) * " << this->Multiplier() << "; " << endl;
        }
		fout << spc << "return arg;" << endl;
		fout << "}" << endl << endl;
    }

    if ( !(this->WriteFunctionCode().empty()) )
    {
        fout << "void " << deviceName << "::set_" << this->Name() << "(" << dataType << " arg) {" << endl;
		for (int i = 1; i <= this->Count(); i++)
		{
			fout << spc << "uint16_t& r" << i << " = r[" << (i-1) << "];" << endl;
		}
		fout << spc << this->WriteFunctionCode() << endl;
		fout << spc << "errno = 0;" << endl;
		if (this->Count() == 1)
		{
			fout << spc << "if (modbus_write_register(md," << this->Addresses() << ",r[0]) == -1) {" << endl;
			fout << spc << spc << "throw modbus_exception(errno,modbus_strerror(errno));" << endl;
			fout << spc << "}" << endl;
		}
		else
		{
			fout << spc << "if (modbus_write_registers(md," 
				<< this->Addresses() << "," << this->Count() << ",r) == -1) {" << endl;
			fout << spc << spc << "throw modbus_exception(errno,modbus_strerror(errno));" << endl;
			fout << spc << "}" << endl;
		}
		fout << "}" << endl << endl;
    }

}


