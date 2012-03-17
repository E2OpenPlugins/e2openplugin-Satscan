from Plugins.Plugin import PluginDescriptor

from Screens.Screen import Screen
from Screens.ServiceScan import ServiceScan
from Screens.MessageBox import MessageBox
from Screens.DefaultWizard import DefaultWizard

from Components.Label import Label
from Components.TuneTest import Tuner
from Components.ConfigList import ConfigListScreen
from Components.ProgressBar import ProgressBar
from Components.Pixmap import Pixmap
from Components.Sources.StaticText import StaticText
from Components.ActionMap import NumberActionMap, ActionMap
from Components.NimManager import nimmanager, getConfigSatlist
from Components.config import config, ConfigSubsection, ConfigSelection, ConfigYesNo, ConfigInteger, getConfigListEntry, ConfigSlider, ConfigEnableDisable

from Tools.HardwareInfo import HardwareInfo
from Tools.Directories import resolveFilename, SCOPE_DEFAULTPARTITIONMOUNTDIR, SCOPE_DEFAULTDIR, SCOPE_DEFAULTPARTITION

from enigma import eTimer, eDVBFrontendParametersSatellite, eComponentScan, eDVBSatelliteEquipmentControl, eDVBFrontendParametersTerrestrial, eDVBFrontendParametersCable, eConsoleAppContainer, eDVBResourceManager, getDesktop

import time

class Satscan(ConfigListScreen, Screen):
	skin = 	"""
		<screen position="center,center" size="500,390" title="Satscan">
			<ePixmap pixmap="skin_default/buttons/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="skin_default/buttons/green.png" position="150,0" size="140,40" alphatest="on" />

			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" foregroundColor="#ffffff" transparent="1"/>
			<widget source="key_green" render="Label" position="150,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" foregroundColor="#ffffff" transparent="1"/>

			<widget name="config"	position="0,56"		font="Regular;20" size="500,150" scrollbarMode="showOnDemand" />
			<widget name="text"		position="0,214"	font="Regular;20" size="500,24"	 halign="center" />
		</screen>
		"""

	def KeyNone(self):
		None

	def callbackNone(self, *retval):
		None

	def OpenFrontend(self):
		frontend = None
		resource_manager = eDVBResourceManager.getInstance()
		if resource_manager is None:
			print "get resource manager instance failed"
		else:
			self.raw_channel = resource_manager.allocateRawChannel(int(self.select_nim.value))

			if self.raw_channel is None:
				print "allocateRawChannel failed"
			else:
				frontend = self.raw_channel.getFrontend()
				if frontend is None:
					print "getFrontend failed"
		return(frontend)

	def GetI2CBusFromSlot(self, slot_number):
		##self.i2c_mapping_table = {0:2, 1:3, 2:1, 3:0}
		self.i2c_mapping_table = [2, 3, 1, 0]

		i2cbus = nimmanager.getI2CDevice(slot_number)

		#print "*** GetI2CBusFromSlot(1), i2cbus = ", i2cbus

		if i2cbus is not None and i2cbus >= 0:
			return i2cbus

		# hack for VU+
		if slot_number >= 0 and slot_number < 4:
			i2cbus = self.i2c_mapping_table[slot_number]
		else:
			i2cbus = -1

		#print "*** GetI2CBusFromSlot(2), i2cbus = ", i2cbus

		return i2cbus

	def SelectedNimToList(self, selected):
		current		= 0
		disabled	= 0

		for all_dvbs_pos in self.all_pos_per_dvbs_nim:
			if self.all_pos_per_dvbs_nim[current] == None:
				disabled = disabled + 1
			if current == int(selected):
				return current - disabled
			current = current + 1
		return -1

	def __init__(self, session): 
		Screen.__init__(self, session)

		self.logfile				= open("/tmp/satscan.log", "w+", 0)

		self.scan_circular		= ConfigYesNo(default = False)
		self.scan_transponders	= ConfigYesNo(default = False)
		self.scan_clearservices	= ConfigYesNo(default = False)
		self.scan_fta			= ConfigYesNo(default = False)

		self.current_service		= self.session.nav.getCurrentlyPlayingServiceReference()
		self.all_pos_per_dvbs_nim	= []

		nimmanager.enumerateNIMs()

		for nim_slot in nimmanager.nim_slots:
			if nim_slot.isCompatible("DVB-S"):
				self.all_pos_per_dvbs_nim.append(nimmanager.getSatListForNim(nim_slot.slot))
			else:
				self.all_pos_per_dvbs_nim.append(None)

		#print "*** all_pos_per_dvbs_nim: ", self.all_pos_per_dvbs_nim

		self.current_orb_pos = 192
		current_service = self.session.nav.getCurrentService()

		if current_service is not None:
			feinfo = current_service.frontendInfo()
			if feinfo is not None:
				fedata = feinfo.getAll(True)
				if fedata.get("tuner_type", "UNKNOWN") == "DVB-S":
					self.current_orb_pos  = fedata.get("orbital_position", 0);

		selectable_nims = []
		for nim in nimmanager.nim_slots:
			if nim.config_mode == "nothing":
				continue
			if nim.config_mode == "advanced" and len(nimmanager.getSatListForNim(nim.slot)) < 1:
				continue
			if nim.config_mode in ("loopthrough", "satposdepends"):
				root_id = nimmanager.sec.getRoot(nim.slot_id, int(nim.config.connectedTo.value))
				if nim.type == nimmanager.nim_slots[root_id].type: # check if connected from a DVB-S to DVB-S2 Nim or vice versa
					continue
			if nim.isCompatible("DVB-S"):
				selectable_nims.append((str(nim.slot), nim.friendly_full_description))

		self.select_nim = ConfigSelection(choices = selectable_nims)

		self.positions_config_list = []
		for nim_slot in nimmanager.nim_slots:
			if nim_slot.isCompatible("DVB-S"):
				self.positions_config_list.append(getConfigSatlist(self.current_orb_pos, self.all_pos_per_dvbs_nim[nim_slot.slot]))

		self.config_list = []
		ConfigListScreen.__init__(self, self.config_list)

		if self.select_nim.value != None and self.select_nim.value != "" :
			self["actions"] = ActionMap(["OkCancelActions", "ShortcutActions", "ColorActions" ],
			{
				"red":		self.keyCancel,
				"green":	self.keyGo,
				"ok":		self.keyGo,
				"cancel":	self.keyCancel,
			}, -2)

			self["key_red"]		= StaticText(_("Exit"))
			self["key_green"]	= StaticText(_("Start"))
			self["text"]		= Label(_("Press OK to start scanning"))

			self.FillConfigList()
		else:
			self["actions"] = ActionMap(["OkCancelActions", "ShortcutActions", "ColorActions" ],
			{
				"red": self.keyCancel,
				"green": self.KeyNone,
				"ok": self.KeyNone,
				"cancel": self.keyCancel,
			}, -2)

			self["key_red"]		= StaticText(_("Exit"))
			self["key_green"]	= StaticText(" ")
			self["text"]		= Label(_("Tuner not set up, can't scan"))

	def FillConfigList(self):
		self.config_list = []
		self.multiscanlist = []
		index_to_scan = int(self.select_nim.value)

		self.tunerEntry = getConfigListEntry(_("Tuner"), self.select_nim)
		self.config_list.append(self.tunerEntry)
		
		if self.select_nim == [ ]:
			return
		
		nim = nimmanager.nim_slots[index_to_scan]

		if not nim.isCompatible("DVB-S"):
			return

		self.config_list.append(getConfigListEntry(_('Satellite'), self.positions_config_list[self.SelectedNimToList(index_to_scan)]))
		self.config_list.append(getConfigListEntry(_("Scan circular polarisation"), self.scan_circular))
		self.config_list.append(getConfigListEntry(_("Scan found transponders"), self.scan_transponders))
		self.config_list.append(getConfigListEntry(_("Clear position before scan"), self.scan_clearservices))
		self.config_list.append(getConfigListEntry(_("Scan only FTA services"), self.scan_fta))
		self["config"].list = self.config_list
		self["config"].l.setList(self.config_list)

		self.scan_transponders.setValue(True)
			
	def UpdateConfigListPositions(self):
		cur = self["config"].getCurrent()
		if cur == self.tunerEntry:
			self.FillConfigList()

	def keyLeft(self):
		ConfigListScreen.keyLeft(self)
		self.UpdateConfigListPositions()

	def keyRight(self):
		ConfigListScreen.keyRight(self)
		self.UpdateConfigListPositions()
			
	def keyCancel(self):
		self.session.nav.playService(self.current_service)
		for x in self["config"].list:
			x[1].cancel()
		self.close()

	def PolarisationFirst(self):
		return 0

	def PolarisationLast(self):
		return 1

	def PolarisationToEnigma(self, pol_id):
		pol_tab_nc	= [ eDVBFrontendParametersSatellite.Polarisation_Horizontal, 	eDVBFrontendParametersSatellite.Polarisation_Vertical ]
		pol_tab_c	= [ eDVBFrontendParametersSatellite.Polarisation_CircularLeft,	eDVBFrontendParametersSatellite.Polarisation_CircularRight ]

		if pol_id == 0 or pol_id == 1:
			if self.scan_circular.value:
				return pol_tab_c[pol_id]
			else:
				return pol_tab_nc[pol_id]
		else:
			return -1

	def PolarisationToString(self, pol_id):
		pol_tab_nc	= [ "horizontal", 		"vertical" ]
		pol_tab_c	= [ "circular left",	"circular right" ]

		if pol_id == 0 or pol_id == 1:
			if self.scan_circular.value:
				return pol_tab_c[pol_id]
			else:
				return pol_tab_nc[pol_id]
		else:
			return "unknown polarisation"

	def PolarisationToShortString(self, pol_id):
		pol_tab_nc	= [ "H", "V" ]
		pol_tab_c	= [ "L", "R" ]

		if pol_id == 0 or pol_id == 1:
			if self.scan_circular.value:
				return pol_tab_c[pol_id]
			else:
				return pol_tab_nc[pol_id]
		else:
			return "U"

	def LOFFirst(self):
		return 0

	def LOFLast(self):
		return 1

	def LOFToFreq(self, lof_id):
		if lof_id == 0:
			return 11015
		if lof_id == 1:
			return 12515
		return 0

	def LOFToString(self, lof_id):
		if lof_id == 0:
			return "low"
		if lof_id == 1:
			return "high"
		return "unknown lof"

	def PositionToString(self, pos):
		if pos < 1800:
			return "%.1fE" % (float(pos) / 10)
		return "%.1fW" % (360 - (float(pos) / 10))

	def PositionToInt(self, pos):
		if pos < 1800:
			return pos
		return pos - 3600

	def keyGo(self):
		selected_nim			= int(self.SelectedNimToList(self.select_nim.value))
		selected_position		= self.positions_config_list[selected_nim].index
		nim_positions_list		= [self.all_pos_per_dvbs_nim[int(self.select_nim.value)][selected_position]]
		self.position			= nim_positions_list[0][0]
		self.position_name		= nim_positions_list[0][1]

		self.frontend = self.OpenFrontend()
		if self.frontend is None:
			self.oldref = self.session.nav.getCurrentlyPlayingServiceReference()
			self.session.nav.stopService()
			self.frontend = self.OpenFrontend()
		if self.frontend is None:
			print "*** cannot open frontend"
			return

		self.i2cbus = self.GetI2CBusFromSlot(int(self.select_nim.value))

		if self.i2cbus < 0:
			print "*** Can't find i2c bus for this nim"
			return

		#print "*** selected_nim =", selected_nim
		#print "*** selected_position =", selected_position
		#print "*** nim_positions_list =", nim_positions_list
		#print "*** position =", self.PositionToString(self.position), "(", self.position, ")"
		#print "*** position_name =", self.position_name

		self.tuner = Tuner(self.frontend)

		self.polarisation			= self.PolarisationFirst()
		self.lof					= self.LOFFirst()
		self.enigma_transponders	= []
		self.text_transponders		= []
		self.xml_transponders		= []

		self.status_screen = self.session.openWithCallback(self.CallbackStatusScreenDone, SatscanStatus, self)

	def CallbackStatusScreenDone(self):

		if self.frontend:
			self.frontend = None
			del self.raw_channel
			self.raw_channel = None

		#print "*** text transponders:", self.text_transponders
		sorted_transponders = sorted(self.text_transponders, key=lambda entry: entry["freq"])
		# print "*** sorted text transponders:", sorted_transponders

		datafile = open("/tmp/satscan.data", "w+")
		for transponder in sorted_transponders:
			datafile.write("%s %d %s %s %s %d %s %s %s %s\n" \
					% (transponder["pos"], transponder["freq"], transponder["pol"], transponder["system"], transponder["mod"],
					transponder["sr"], transponder["fec"], transponder["inv"], transponder["pilot"], transponder["rolloff"]))
		datafile.close()

		#print "*** xml transponders:", self.xml_transponders
		sorted_transponders = sorted(self.xml_transponders, key=lambda entry: entry["freq"])
		#print "*** sorted xml transponders:", sorted_transponders

		xmlfile = open('/tmp/satscan-%s.xml' % (self.PositionToString(self.position)), "w+")
		xmlfile.write('<satellites>\n')
		xmlfile.write('    <sat name="%s" flags="0" position="%d">\n' % (self.position_name, self.PositionToInt(self.position)))
		for transponder in sorted_transponders:
			xmlfile.write('        <transponder frequency="%d" symbol_rate="%d" polarization="%d" fec_inner="%d" system="%d" modulation="%d" />\n' \
					% (transponder["freq"], transponder["sr"], transponder["pol"], transponder["fec"], transponder["system"], transponder["mod"]))
		xmlfile.write('    </sat>\n')
		xmlfile.write('</satellites\n')
		xmlfile.close()

		self.logfile.close()

		if self.scan_transponders.value:
			self.ScanTransponders()

		self.close(True)

	def ScanTransponders(self):

		if self.enigma_transponders == []:
			return

		flags = 0

		if self.scan_clearservices.value:
			flags |= eComponentScan.scanRemoveServices
		else:
			flags |= eComponentScan.scanDontRemoveUnscanned

		if self.scan_fta.value:
			flags |= eComponentScan.scanOnlyFree

		print "*** scanning transponders:"

		for transponder in self.enigma_transponders:
			print "-->", transponder.orbital_position, transponder.polarisation, transponder.frequency, \
					transponder.symbol_rate, transponder.system, transponder.inversion, transponder.pilot, transponder.pilot, \
					transponder.fec, transponder.modulation, transponder.rolloff

		self.session.open(ServiceScan, [{"transponders": self.enigma_transponders, "feid": int(self.select_nim.value), "flags": flags}])

class SatscanStatus(Screen):
	skin = """
		<screen position="center,center" size="500,390" title="Satscan progress">
			<widget name="frontend" pixmap="skin_default/icons/scan-s.png" position="0,0" size="64,64" transparent="1" alphatest="on" />
			<widget name="scan_state" position="82,0" zPosition="2" size="414,66" font="Regular;18" />
			<widget name="scan_progress" position="0,74" size="500,15" pixmap="skin_default/progress_big.png" />
			<widget name="info" position="0,100" size="500,400" font="Regular;18" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, parent):
		Screen.__init__(self, session)

		self.parent				= parent
		self["frontend"]		= Pixmap()
		self["scan_state"]		= Label(_("scan state"))
		self["scan_progress"]	= ProgressBar()
		self["info"]			= Label()

		self["actions"] = ActionMap(["OkCancelActions"],
		{
			"cancel":	self.StatusOnCancel
		})

		self.log		= ""
		self.progress	= 0

		self.onFirstExecBegin.append(self.StatusStartScanRound)

	def StatusOnCancel(self):
		self.close()

	def StatusStartScanRound(self):
		parent = self.parent

		status = "Position: %s\nPolarisation: %s\nBand: %s\n" % \
				 (parent.PositionToString(parent.position), \
				  parent.PolarisationToString(parent.polarisation), \
				  parent.LOFToString(parent.lof))

		self["scan_state"].setText(status)

		parent.progress = (parent.polarisation + (parent.lof * 2)) * 25
		self["scan_progress"].setValue(parent.progress)

		parent.tuner.tune((parent.LOFToFreq(parent.lof), 0, parent.PolarisationToEnigma(parent.polarisation), 0, 0, parent.position, eDVBFrontendParametersSatellite.System_DVB_S, 0, 0, 0))

		cmdpre		= 'echo "wait (5 seconds)" && sleep 5 && echo start scanning && '
		cmdbinary	= 'vuplus_blindscan %d %d %d %d %d %d %d %s' % (950, 2150, 2, 45, parent.polarisation, parent.lof, int(parent.select_nim.value), parent.i2cbus)
		cmdpost		= ' && echo finished'
		cmd			= ''

		if (parent.polarisation == parent.PolarisationFirst()) and (parent.lof == parent.LOFFirst()):
			cmd = cmdpre + cmd

		cmd = cmd + cmdbinary

		if (parent.polarisation == parent.PolarisationLast()) and (parent.lof == parent.LOFLast()):
			cmd = cmd + cmdpost

		print 'prepared command: "%s"' % (cmd)

		parent.app_container = eConsoleAppContainer()
		parent.app_container.appClosed.append(self.StatusAppContainerClose)
		parent.app_container.dataAvail.append(self.StatusAppContainerDataAvail)
		parent.app_container.execute(cmd)

	def StatusAppContainerDataAvail(self, str):

		enigma_system = {
			"DVB-S":	eDVBFrontendParametersSatellite.System_DVB_S,
			"DVB-S2":	eDVBFrontendParametersSatellite.System_DVB_S2
		}

		enigma_modulation = {
			"QPSK":	eDVBFrontendParametersSatellite.Modulation_QPSK,
			"8PSK":	eDVBFrontendParametersSatellite.Modulation_8PSK
		}

		enigma_inversion =	{
			"INVERSION_OFF":	eDVBFrontendParametersSatellite.Inversion_Off,
			"INVERSION_ON":		eDVBFrontendParametersSatellite.Inversion_On,
			"INVERSION_AUTO":	eDVBFrontendParametersSatellite.Inversion_Unknown
		}

		enigma_fec = {
			"FEC_AUTO":	eDVBFrontendParametersSatellite.FEC_Auto,
			"FEC_1_2":	eDVBFrontendParametersSatellite.FEC_1_2,
			"FEC_2_3":	eDVBFrontendParametersSatellite.FEC_2_3,
			"FEC_3_4":	eDVBFrontendParametersSatellite.FEC_3_4,
			"FEC_5_6":	eDVBFrontendParametersSatellite.FEC_5_6,
			"FEC_7_8":	eDVBFrontendParametersSatellite.FEC_7_8,
			"FEC_8_9":	eDVBFrontendParametersSatellite.FEC_8_9,
			"FEC_3_5":	eDVBFrontendParametersSatellite.FEC_3_5,
			"FEC_9_10":	eDVBFrontendParametersSatellite.FEC_9_10,
			"FEC_NONE":	eDVBFrontendParametersSatellite.FEC_None
		}

		enigma_rollof = {
			"ROLLOFF_20":	eDVBFrontendParametersSatellite.RollOff_alpha_0_20,
			"ROLLOFF_25":	eDVBFrontendParametersSatellite.RollOff_alpha_0_25,
			"ROLLOFF_35":	eDVBFrontendParametersSatellite.RollOff_alpha_0_35
		}

		enigma_pilot = {
			"PILOT_ON":		eDVBFrontendParametersSatellite.Pilot_On,
			"PILOT_OFF":	eDVBFrontendParametersSatellite.Pilot_Off
		}

		parent = self.parent

		for line in str.splitlines():
			#print "-->", line, "<--"

			if line.startswith("OK"):
				data = line.split()
				print "cnt:", len(data), ", data:", data
				if len(data) >= 10 and data[0] == "OK":
					try:
						transponder						= eDVBFrontendParametersSatellite()
						transponder.orbital_position	= parent.position
						transponder.polarisation		= parent.PolarisationToEnigma(parent.polarisation)
						transponder.frequency			= int(data[2])
						transponder.symbol_rate			= int(data[3])
						transponder.system				= enigma_system[data[4]]
						transponder.inversion			= enigma_inversion[data[5]]
						transponder.pilot				= enigma_pilot[data[6]]
						transponder.fec					= enigma_fec[data[7]]
						transponder.modulation			= enigma_modulation[data[8]]
						transponder.rolloff				= enigma_rollof[data[9]]
						parent.enigma_transponders.append(transponder)

						raw_transponder					= {}
						raw_transponder["pos"]			= parent.PositionToString(parent.position)
						raw_transponder["freq"]			= int(data[2])
						raw_transponder["pol"]			= parent.PolarisationToString(parent.polarisation)
						raw_transponder["system"]		= data[4]
						raw_transponder["mod"]			= data[8]
						raw_transponder["sr"]			= int(data[3])
						raw_transponder["fec"]			= data[7]
						raw_transponder["inv"]			= data[5]
						raw_transponder["pilot"]		= data[6]
						raw_transponder["rolloff"]		= data[9]
						parent.text_transponders.append(raw_transponder)

						xml_transponder					= {}
						xml_transponder["freq"]			= round(int(data[2]) / 1000) * 1000
						xml_transponder["sr"]			= round(int(data[3]) / 1000) * 1000
						xml_transponder["pol"]			= parent.PolarisationToEnigma(parent.polarisation)
						xml_transponder["fec"]			= enigma_fec[data[7]] + 1
						xml_transponder["system"]		= enigma_system[data[4]]
						xml_transponder["mod"]			= enigma_modulation[data[8]]
						parent.xml_transponders.append(xml_transponder)

						message = "found: %d %s %s %s %d %s\n" % (int(data[2]) / 1000, \
								parent.PolarisationToShortString(parent.polarisation), data[4], \
								data[8], int(data[3]) / 1000, data[7])
						
					except:
						message = "invalid data: " + line + "\n"
						pass
				else:
					message = "invalid data: " + line + "\n"
			else:
				message = line + "\n"

			self.log = message + self.log
			self["info"].setText(self.log)

			parent.logfile.write(time.strftime("%Y/%m/%d %H:%M:%S: ") + message)

			parent.progress = parent.progress + 2
			self["scan_progress"].setValue(parent.progress)

	def StatusAppContainerClose(self, retval):
		parent = self.parent

		parent.app_container.sendCtrlC()
		time.sleep(1)
		del parent.app_container

		parent.polarisation = parent.polarisation + 1

		if parent.polarisation > parent.PolarisationLast():
			parent.polarisation	= parent.PolarisationFirst()
			parent.lof			= parent.lof + 1

		if parent.polarisation <= parent.PolarisationLast() and parent.lof <= parent.LOFLast():
			self.StatusStartScanRound()
		else:
			self.close()

def main(session, **kwargs):
	session.open(Satscan)

def SatscanPluginSetup(menuid, **kwargs):
	if menuid == "scan":
		return [(_("Satscan"), main, "satscan", 25)]
	else:
		return []

def Plugins(path, **kwargs):
	plugin_list = [PluginDescriptor(name=_("Satscan"), where = PluginDescriptor.WHERE_MENU, needsRestart = False, fnc = SatscanPluginSetup)]
	return plugin_list
