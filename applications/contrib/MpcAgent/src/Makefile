# GNU gcc compiler
CFLAGS = -O3 -fopenmp -Wall -I${ADEVS}/include ${OMINCLUDE} \
		 -I${SUNDIALS_PATH}/include -I/usr/local/modbus/include/modbus -fPIC
ARCH_LIB = lib64
ARCH_FLAGS = 
CC = g++
ADEVS=${HOME}/Code/adevs-code
SUNDIALS_PATH=/usr/local/sundials
OMHOME=${HOME}/Code/openmodelica/trunk/build
OMINCLUDE=-I${OMHOME}/include/omc
OMLIBS=-L${OMHOME}/lib/omc -L${ADEVS}/src -ladevs -lsundials_kinsol \
	   -L${SUNDIALS_PATH}/lib \
	   -lsundials_nvecserial \
	   -llapack /usr/local/lib/libf2c.a 

.SUFFIXES: .cpp
.cpp.o:
	${CC} ${ARCH_FLAGS} ${CFLAGS} -o $@ -c $<

SIMOBJS = \
	   SimpleControl.o \
	   MPC.o \
	   simtest.o \
	   BuildingModel.o \
	   BuildingModelExt.o \
	   FourZoneBuilding.o \
	   FourZoneBuildingExt.o \
	   CBC.o \
	   CBCExt.o \
	   test_main.o \
	   python_control.o \
	   python_simulated_building.o

CBCOBJS = \
		  MPC.o \
		  python_control.o \
		  python_cbc_building.o

simlibs: objs 
	g++ -shared -fopenmp -o mpc_lib.so MPC.o python_control.o \
		-llapack /usr/local/lib/libf2c.a 
	g++ -shared -fopenmp -o bldg_lib.so FourZoneBuilding.o \
		FourZoneBuildingExt.o \
		python_simulated_building.o simtest.o ${OMLIBS}

cbclibs: ${CBCOBJS}
	g++ ${ARCH_FLAGS} -shared -fopenmp -o mpc_lib.so MPC.o python_control.o \
		-L/usr/${ARCH_LIB}/ -llapack
	g++ ${ARCH_FLAGS} -shared -fopenmp -o bldg_lib.so python_cbc_building.o \
	    -L/usr/local/modbus/lib -lmodbus

sim: objs
	${CC} ${CFLAGS} ${SIMOBJS} ${OMLIBS}

objs: modelica ${SIMOBJS}

modelica:
	${OMHOME}/bin/omc +s +simCodeTarget=Adevs BuildingModel.mo 
	${OMHOME}/bin/omc +s +simCodeTarget=Adevs FourZoneBuilding.mo 
	${OMHOME}/bin/omc +s +simCodeTarget=Adevs CBC.mo 

ctest: 
	${OMHOME}/bin/omc +s +simCodeTarget=Adevs ControlModel.mo HVACModelBase.mo
	${CC} ${CFLAGS} testControlModel.cpp ControlModel.cpp ${OMLIBS}
	
deploy: clean cbclibs 
	cp *.so ../rtunetwork

clean:
	rm -f *.o *.so

