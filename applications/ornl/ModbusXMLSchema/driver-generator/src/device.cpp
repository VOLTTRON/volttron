#include <iostream>
#include <fstream>
#include <cstdlib>
#include <algorithm>

#include "device.h"

using namespace modbus_device;
using namespace std;

Device::Device()
{}

const string& Device::Name()
{
    return name;
}
        
void Device::SetName( const string& Name )
{
    name = Name;
}

const string& Device::Description()
{
    return description;
}

void Device::SetDescription( const string& Description )
{
    description = Description;
}

int Device::FunctionCount()
{
    return functions.size();
}

void Device::AddFunction(const Function* func)
{

    functions.push_back(*func);
}



void Device::WriteHeader()
{
    string deviceName = this->Name();

    // remove spaces
    std::replace( deviceName.begin(), deviceName.end(), ' ', '_');

    // all caps copy
    string deviceNameCaps = deviceName;
    std::transform( deviceNameCaps.begin(), deviceNameCaps.end(), deviceNameCaps.begin(), ::toupper );

    static const char* spc = "   ";

    // create header file
	ofstream fout( string( deviceName+".h" ).c_str() );

    // echo header info
	fout << "#ifndef __" << deviceNameCaps << "_H__" << endl;
	fout << "#define __" << deviceNameCaps << "_H__" << endl;
    fout << endl;
	fout << "#include \"mdl.h\"" << endl;
	fout << endl;

    // echo class
    fout << "/* " << this->Name() << endl;
    fout << "   " << this->Description() << " */" << endl;
	fout << "class " << deviceName << " {" << endl;
	fout << "public: " << endl;

    // echo constructors
	fout << spc << "/* Connect to a serial device */" << endl;
	fout << spc << deviceName <<
		"(int deviceID, const char* serial_port, int baud, char parity='N', int data_bit=8, int stop_bit=1);" << endl << endl;
	fout << spc << "/* Connect to a TCP/IP device */" << endl;
	fout << spc << deviceName << "(const char* addr, int port);" << endl << endl;

    // echo destructor
	fout << spc << "/* Close any open connection and delete the device */" << endl;
	fout << spc << "~" << deviceName << "();" << endl;

    // iterate over the functions and echo function declations
	vector<Function>::iterator iter;
    for ( iter = functions.begin(); iter != functions.end(); ++iter ) 
    {
        iter->WriteHeader(fout);
	}

    // echo the private block
    fout << endl;
	fout << "private: " << endl;
	fout << spc << "modbus_t *md;" << endl;

    // TODO: understand max register count
	fout << spc << "uint16_t r[" << this->FunctionCount() << "];" << endl;
	fout << "};" << endl;

	fout << endl << "#endif" << endl;

    // done creating header
	fout.close();   
}

void Device::WriteSource()
{
    string deviceName = this->Name();

    // remove spaces
    std::replace( deviceName.begin(), deviceName.end(), ' ', '_');

    // all caps copy
    string deviceNameCaps = deviceName;
    std::transform( deviceNameCaps.begin(), deviceNameCaps.end(), deviceNameCaps.begin(), ::toupper );

    static const char* spc = "   ";

    // create source file
	ofstream fout( string( deviceName+".cc" ).c_str() );

    // echo includes
	fout << "#include \"" << deviceName <<".h\"" << endl;
    fout << "#include <cerrno>" << endl;
	fout << endl;

    // echo constructors
	fout << deviceName << "::" << deviceName << "(int deviceID, const char* serial_port, int baud, char parity, int data_bit, int stop_bit) { " << endl;
	fout << spc << "errno = 0;" << endl;
	fout << spc << "md = modbus_new_rtu(serial_port,baud,parity,data_bit,stop_bit);" << endl;
	fout << spc << "if (md == NULL) {" << endl;
	fout << spc << spc << "throw modbus_exception(errno,modbus_strerror(errno));" << endl;
	fout << spc << "}" << endl;
	fout << spc << "if (modbus_set_slave(md,deviceID) == -1) {" << endl;
	fout << spc << spc << "throw modbus_exception(errno,modbus_strerror(errno));" << endl;
	fout << spc << "}" << endl;
	fout << spc << "if (modbus_connect(md) == -1) {" << endl;
	fout << spc << spc << "throw modbus_exception(errno,modbus_strerror(errno));" << endl;
	fout << spc << "}" << endl;
	fout << "}" << endl << endl;
	fout << deviceName << "::" << deviceName << "(const char* addr, int port) { " << endl;
	fout << spc << "errno = 0;" << endl;
	fout << spc << "md = modbus_new_tcp(addr,port);" << endl;
	fout << spc << "if (md == NULL) {" << endl;
	fout << spc << spc << "throw modbus_exception(errno,modbus_strerror(errno));" << endl;
	fout << spc << "}" << endl;
	fout << spc << "if (modbus_connect(md) == -1) {" << endl;
	fout << spc << spc << "throw modbus_exception(errno,modbus_strerror(errno));" << endl;
	fout << spc << "}" << endl;
	fout << "}" << endl << endl;
	fout << deviceName << "::~" << deviceName << "() { " << endl;
	fout << spc << "if (md != NULL) {" << endl;
	fout << spc << spc << "modbus_close(md);" << endl;
	fout << spc << spc << "modbus_free(md);" << endl;
	fout << spc << "}" << endl;
	fout << "}" << endl << endl;

    // iterate over the functions and echo function definitions
	vector<Function>::iterator iter;
    for ( iter = functions.begin(); iter != functions.end(); ++iter ) 
        iter->WriteSource(deviceName, fout);

    // done creating source
	fout.close();
}

void Device::ReadXMLFile(const string& filename)
{
    try
    {
        xmlpp::DomParser parser;
        parser.set_substitute_entities();

        parser.parse_file(filename);

        if(parser)
        {
            // this should be the 'device' node
            const xmlpp::Node* deviceNode = parser.get_document()->get_root_node(); 

            // read device name
            xmlpp::Node::NodeList list = deviceNode->get_children("name");
            for(xmlpp::Node::NodeList::iterator iter = list.begin(); iter != list.end(); ++iter)
            {
                cout<<"Device: " << "  " << getNodeValue(*iter) << endl;
                this->SetName( getNodeValue(*iter) );
            }

            // read description
            list = deviceNode->get_children("description");
            for(xmlpp::Node::NodeList::iterator iter = list.begin(); iter != list.end(); ++iter)
            {
                cout<<"Description: " << getNodeValue(*iter) << endl;
                this->SetDescription( getNodeValue(*iter) );
            }

            // iterate and read functions
            list = deviceNode->get_children("function");
            for(xmlpp::Node::NodeList::iterator iter = list.begin(); iter != list.end(); ++iter)
            {
                cout<<endl<<"Reading " << (*iter)->get_name() << endl;
                readFunction( *iter );
            }
        }
    }
    catch(const std::exception& ex)
    {
        std::cout << "Exception caught: " << ex.what() << std::endl;
    }

}

void Device::readFunction(const xmlpp::Node* functionNode)
{
    Function* func = new Function();

    xmlpp::Node::NodeList listElements = functionNode->get_children();
    for(xmlpp::Node::NodeList::iterator iter = listElements.begin(); iter != listElements.end(); ++iter)
    {
        xmlpp::ContentNode* nodeContent = dynamic_cast<xmlpp::ContentNode*>( *iter );
        if(!nodeContent)
        {
            cout<<"    " << (*iter)->get_name() << " : " << getNodeValue(*iter) << endl;
            string name = (*iter)->get_name();
            string value = getNodeValue(*iter);
            if( name == "name" )
                func->SetName( value );
		    if( name == "description" )
                func->SetDescription( value );
		    if( name == "addresses" )
                func->SetAddresses( value );
		    if( name == "length" )
                func->SetLength( value );
		    if( name == "count" )
                func->SetCount( atoi(value.c_str()) );
		    if( name == "format" )
                func->SetFormat( value );
		    if( name == "block_label" )
                func->SetBlockLabel( value );
		    if( name == "multiplier" ) 
                func->SetMultiplier( atof(value.c_str()) );
		    if( name == "read_function_code" )
                func->SetReadFunctionCode( value );
		    if( name == "write_function_code" )
                func->SetWriteFunctionCode( value );
        }
    }

    this->AddFunction(func);
}

std::string Device::getNodeValue(const xmlpp::Node* node)
{
    xmlpp::Node::NodeList list = node->get_children();
    for(xmlpp::Node::NodeList::iterator iter = list.begin(); iter != list.end(); ++iter)
    {
        xmlpp::TextNode* nodeText = dynamic_cast<xmlpp::TextNode*>(*iter);
        if(nodeText)
        {
            return nodeText->get_content();
        }
    }
    return "";
}



