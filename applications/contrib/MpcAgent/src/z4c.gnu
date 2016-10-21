reset
set xlabel 'days'
set ylabel 'deg C'
set y2label 'net Joules'
set y2tics 
plot 'z4/simple/bldgm.dat' using ($1/86400):2 with lines title 'simple 1 - deg C',\
'' using ($1/86400):3 with lines title 'simple 2 - deg C',\
'' using ($1/86400):4 with lines title 'simple 3 - deg C',\
'' using ($1/86400):5 with lines title 'simple 4 - deg C',\
'' using ($1/86400):7 axis x1y2 with lines title 'simple - net J',\
'z4/mpc/bldgm.dat' using ($1/86400):2 with lines title 'mpc 1 - deg C',\
'' using ($1/86400):3 with lines title 'mpc 2 - deg C',\
'' using ($1/86400):4 with lines title 'mpc 3 - deg C',\
'' using ($1/86400):5 with lines title 'mpc 4 - deg C',\
'' using ($1/86400):7 axis x1y2 with lines title 'mpc - net J'
