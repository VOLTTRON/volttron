reset
set multiplot layout 3,1
set xlabel 'days'
set ylabel 'deg C'
set y2label 'J
set y2tics
plot 'bldgm.dat' using ($1/86400):2 with lines title 'Z1',\
'' using ($1/86400):3 with lines title 'Z2',\
'' using ($1/86400):4 with lines title 'Z3',\
'' using ($1/86400):5 with lines title 'Z4',\
'' using ($1/86400):6 with lines title 'Z5',\
'' using ($1/86400):7 with lines title 'Out',\
'' using ($1/86400):8 with lines axis x1y2 title 'Net J'
unset y2tics 
unset y2label
set ylabel 'heat mode'
plot 'bldgm.dat' using ($1/86400):9 with steps title 'z1',\
'' using ($1/86400):11 with steps title 'z2',\
'' using ($1/86400):13 with steps title 'z3',\
'' using ($1/86400):15 with steps title 'z4',\
'' using ($1/86400):17 with steps title 'z5'
set ylabel 'cool mode'
plot 'bldgm.dat' using ($1/86400):10 with steps title 'z1',\
'' using ($1/86400):12 with steps title 'z2',\
'' using ($1/86400):14 with steps title 'z3',\
'' using ($1/86400):16 with steps title 'z4',\
'' using ($1/86400):18 with steps title 'z5'
unset multiplot
