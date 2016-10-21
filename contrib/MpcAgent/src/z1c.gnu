reset
set xlabel 'days'
set ylabel 'deg C'
set y2label 'net Joules'
set y2tics 
plot 'z1/simple/bldgm.dat' using ($1/86400):2 with lines title 'simple - deg C',\
'' using ($1/86400):4 axis x1y2 with lines title 'simple - net J',\
'z1/mpc/bldgm.dat' using ($1/86400):2 with lines title 'mpc - deg C',\
'' using ($1/86400):4 axis x1y2 with lines title 'mpc - net J'
