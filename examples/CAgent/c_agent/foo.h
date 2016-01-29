#ifndef _FOO_
#define _FOO_

#define ELEMENT_ON 1
#define ELEMENT_OFF 0

#define AMBIENT_TEMP 70 /* F */

int heating_element_status();
float water_temperature();

void set_temperature(int);
void set_element_threshold(int);


#endif
