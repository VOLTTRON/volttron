
LIBMODBUS_HOME = /usr/local/libmodbus
# Compiler flags
CFLAGS = -g -Wall -I${LIBMODBUS_HOME}
LIBXML_FLAGS = $(shell pkg-config --cflags --libs glibmm-2.4 libxml++-2.6)
CXX = g++
COMPILER_TARGET=mdl2code

COMPILER_SRC = \
	function.cpp \
	device.cpp \
	main.cpp

COMPILER_HEADERS = \
	function.h \
	device.h 

all: ${COMPILER_HEADERS} ${COMPILER_SRC} 
	${CXX} ${CFLAGS} -o ${COMPILER_TARGET} ${COMPILER_SRC} ${LIBXML_FLAGS}

clean:
	rm -rf ${COMPILER_TARGET} *.o

