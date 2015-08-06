class BuildingModel 
	// Parameters
	parameter Real C1 = 9.356E5; // kJ / deg C
	parameter Real C2 = 2.970E6; // kJ / deg C
	parameter Real C3 = 6.695E5; // kJ / deg C
	parameter Real K1 = 16.48; // kW / deg C
	parameter Real K2 = 108.5; //  kW / deg C
	parameter Real K3 = 5; // kW / deg C
	parameter Real K4 = 30.5; // kW / deg C
	parameter Real K5 = 23.04; // kW / deg C
	parameter Real solarGain = 1.0;
	parameter Real heatHvac = 100.0; // base heating power (>= 0) [kW]
	parameter Real coolHvac = -100.0; // base cooling power (>= 0) [kW]
	// Model variables
	Real t1(start=25,fixed=true); // room air temperature [deg C]
	Real t2(start=25,fixed=true); // interior-wall surface temperature [deg C]
	Real t3(start=25,fixed=true); // exterior-wall core temperature [deg C]
	parameter Integer coolStage = 0; // 0 (off), 1, 2 
	parameter Integer heatStage = 0; // 0 (off), 1, 2 
	Real day; // Current day of simulation time
	Real dayCycle; // Current part of daily period
	Real dayHour; // Current 
	Real d1; // outside air temperature [deg C]
	Real d2; // solar radiation [kW]
	Real d3; // internal heat sources [kW]
	Real energyUsed(start=0,fixed=true); // energy consumed by HVAC [kJ]
	Real solarPower;
equation
	der(t1) = (1/C1)*((K1+K2)*(t2-t1)+K5*(t3-t1)
			+ K3*(d1-t1)+heatHvac*heatStage+coolHvac*coolStage+d2+d3);
	der(t2) = (1/C2)*((K1+K2)*(t1-t2)+d2);
	der(t3) = (1/C3)*(K5*(t1-t3)+K4*(d1-t3));
	day = time/(24.0*60.0*60.0);
	dayCycle = 0.5+cos(2*3.14*day)/2;
	dayHour = (day-floor(day))*24;
	d1 = 0+25*dayCycle;
	d2 = 40*dayCycle;
	d3 = if dayHour >= 8 and dayHour <= 18 then 80 else 0;
	der(energyUsed) = abs(heatHvac*heatStage)+abs(coolHvac*coolStage);
	solarPower = solarGain*d2;
end BuildingModel;
