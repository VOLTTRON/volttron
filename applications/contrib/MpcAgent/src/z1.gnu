reset
set xlabel 'days'
set ylabel 'deg C'
set y2label 'net Joules'
set y2tics 
plot 'bldgm.dat' using ($1/86400):2 with lines title '1 - deg C',\
'' using ($1/86400):4 axis x1y2 with lines title 'net J'
