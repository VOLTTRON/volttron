connector ZonePin
	Real T; // Temperature on the pin
	flow Real Q; // Heat flow through the pin
end ZonePin;

model ZoneConnector
	ZonePin pa, pb;
	Real T, Q;
	parameter Real KInterZone = 1000.0; // kW / degC
equation
	0 = pa.Q + pb.Q;
	T = pa.T - pb.T;
	Q = pa.Q;
	Q = KInterZone*T;
end ZoneConnector;

model Zone
	// Parameters
	parameter Real C1 = 9.356E5; // kJ / deg C
	parameter Real C2 = 2.970E6; // kJ / deg C
	parameter Real C3 = 6.695E5; // kJ / deg C
	parameter Real K1 = 16.48; // kW / deg C
	parameter Real K2 = 108.5; //  kW / deg C
	parameter Real K3 = 5; // kW / deg C
	parameter Real K4 = 30.5; // kW / deg C
	parameter Real K5 = 23.04; // kW / deg C
	parameter Real heatHvac = 100.0; // base heating power (>= 0) [kW]
	parameter Real coolHvac = -100.0; // cooling power (<= 0) [kW]
	// Model variables
	Real t1(start=25,fixed=true); // room air temperature [deg C]
	Real t2(start=25,fixed=true); // interior-wall surface temperature [deg C]
	Real t3(start=25,fixed=true); // exterior-wall core temperature [deg C]
	parameter Integer heatStage = 0; // 0 (off), 1, 2
	parameter Integer coolStage = 0; // 0 (off), 1, 2
	input Real dayHour; // Current 
	input Real d1; // outside air temperature [deg C]
	input Real d2; // solar radiation [kW]
	Real d3; // internal heat sources [kW]
	Real energyUsed(start=0,fixed=true); // energy consumed by HVAC [kJ]
	ZonePin pin; // Connector for adjacent zones
equation
	pin.T = t1;
	der(t1) = (1/C1)*((K1+K2)*(t2-t1)+K5*(t3-t1)
			+ K3*(d1-t1)+heatStage*heatHvac+coolStage*coolHvac+d2+d3
			+ pin.Q);
	der(t2) = (1/C2)*((K1+K2)*(t1-t2)+d2);
	der(t3) = (1/C3)*(K5*(t1-t3)+K4*(d1-t3));
//	d3 = if dayHour >= 8 and dayHour <= 18 then 80 else 0;
	d3 = 0; // 160.0*sin(2.0*3.14*0.25*dayHour);
	der(energyUsed) = abs(heatStage*heatHvac)+abs(coolStage*coolHvac);
end Zone;

model ExteriorConditions
	Real day; // Current day of simulation time
	Real dayCycle; // Current part of daily period
	output Real dayHour; // Current 
	output Real d1; // outside air temperature [deg C]
	output Real d2; // solar radiation [kW]
equation
	d1 = 10+15*dayCycle;
	d2 = 40*dayCycle;
	day = time/(24.0*60.0*60.0);
	dayCycle = 0.5+cos(2*3.14*day)/2;
	dayHour = (day-floor(day))*24;
end ExteriorConditions;

model FourZoneBuilding
	Zone z1, z2, z3, z4, znoise(K2=10,C2=1E4);
	ZoneConnector link[5];
	ExteriorConditions outdoor;
equation
	connect(outdoor.dayHour,znoise.dayHour);
	connect(outdoor.d1,znoise.d1);
	connect(outdoor.d2,znoise.d2);
	connect(outdoor.dayHour,z1.dayHour);
	connect(outdoor.d1,z1.d1);
	connect(outdoor.d2,z1.d2);
	connect(outdoor.dayHour,z2.dayHour);
	connect(outdoor.d1,z2.d1);
	connect(outdoor.d2,z2.d2);
	connect(outdoor.dayHour,z3.dayHour);
	connect(outdoor.d1,z3.d1);
	connect(outdoor.d2,z3.d2);
	connect(outdoor.dayHour,z4.dayHour);
	connect(outdoor.d1,z4.d1);
	connect(outdoor.d2,z4.d2);
	connect(z1.pin,link[1].pa);
	connect(z2.pin,link[2].pa);
	connect(z3.pin,link[3].pa);
	connect(z4.pin,link[4].pa);
	connect(z1.pin,link[4].pb);
	connect(z2.pin,link[1].pb);
	connect(z3.pin,link[2].pb);
	connect(z4.pin,link[3].pb);
	connect(z1.pin,link[5].pa);
	connect(znoise.pin,link[5].pb);
end FourZoneBuilding;
