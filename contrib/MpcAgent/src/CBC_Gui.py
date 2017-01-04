from Tkinter import *
import threading
import python_building

class ZoneGui:
	def __init__(self,zone,building,root):
		self.frame = Frame(root)
		self.zone = zone
		self.building = building
		# Fan mode
		self.var_fan = StringVar()
		self.var_fan.set("Zone "+str(zone)+" fan")
		self.zone_fan = Label(self.frame,textvariable=self.var_fan)
		self.zone_fan.pack();
		self.list_fan = Listbox(self.frame,exportselection=0,selectmode=SINGLE,height=2)
		self.list_fan.insert(END,"on")
		self.list_fan.insert(END,"auto")
		self.list_fan.selection_set(END)
		self.list_fan.bind('<<ListboxSelect>>',self.select_fan)
		self.list_fan.pack()
		# Cooling deadband
		self.var_cool = StringVar()
		self.var_cool.set("Zone "+str(zone)+" cooling deadband")
		self.zone_cool = Label(self.frame,textvariable=self.var_cool)
		self.zone_cool.pack()
		self.list_cool = Listbox(self.frame,exportselection=0,selectmode=SINGLE,height=15)
		for d in range(1,16):
			self.list_cool.insert(END,str(d))
		self.list_cool.selection_set(END)
		self.list_cool.bind('<<ListboxSelect>>',self.select_heat_cool)
		self.list_cool.pack()
		# Heating deadband
		self.var_heat = StringVar()
		self.var_heat.set("Zone "+str(zone)+" heating deadband")
		self.zone_heat = Label(self.frame,textvariable=self.var_heat)
		self.zone_heat.pack()
		self.list_heat = Listbox(self.frame,exportselection=0,selectmode=SINGLE,height=15)
		for d in range(1,16):
			self.list_heat.insert(END,str(d))
		self.list_heat.selection_set(END)
		self.list_heat.bind('<<ListboxSelect>>',self.select_heat_cool)
		self.list_heat.pack()
		self.frame.pack(side=LEFT)

	def select_fan(self,e):
		mode = self.list_fan.get(self.list_fan.curselection()[0])
		if mode == "auto":
			print self.zone,"fan->auto"
			self.building.set_fan_mode(self.zone,0)
		else:
			print self.zone,"fan->on"
			self.building.set_fan_mode(self.zone,1)
	def select_heat_cool(self,e):
		heat = self.list_cool.get(self.list_heat.curselection()[0])
		cool = self.list_heat.get(self.list_cool.curselection()[0])
		print self.zone,"cool->"+str(cool)+",heat->"+str(heat)
		self.building.set_deadbands(self.zone,float(cool),float(heat))

# User interface for the MPC agent application
class CBC_Gui(threading.Thread):
	def __init__(self,building):
		threading.Thread.__init__(self)
		self.building = building
		self.start()
	def exit(self):
		self.root.quit()
	def run(self):
		self.root=Tk()
		self.root.protocol("WM_DELETE_WINDOW", self.exit)
		self.z1 = ZoneGui(0,self.building,self.root)
		self.z2 = ZoneGui(1,self.building,self.root)
		self.z3 = ZoneGui(2,self.building,self.root)
		self.z4 = ZoneGui(3,self.building,self.root)
		self.root.mainloop()
