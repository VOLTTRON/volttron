'use strict';

var ACTION_TYPES = require('../constants/action-types');
var authorizationStore = require('../stores/authorization-store');
var dispatcher = require('../dispatcher');
var Store = require('../lib/store');
var Immutable = require("immutable");

var devicesStore = new Store();

var _data = {};
var _updatedRow = {};
var _platform;
var _devices = []; // the main list of devices detected for configuration
var _devicesList = {}; // a simple object of known devices
var _settingsTemplate = {};
var _savedRegistryFiles = {};
var _newScan = false;
var _clearConfig = false;
var _reconfiguringDevice = false;
var _reconfiguration = {};
var _scanningComplete = true;
var _warnings = {};
var _keyboard = {
    device: null,
    active: false,
    cmd: null,
    started: false
};
var _focusedDevice = {id: null, address: null};

var _backupPoints = [];

var _defaultKeyProps = ["volttron_point_name", "units", "writable"];

var _placeHolders = Immutable.List([ [
    {"key": "Point_Name", "value": ""},
    {"key": "Volttron_Point_Name", "value": ""},
    {"key": "Units", "value": ""},
    {"key": "Units_Details", "value": "" },
    {"key": "Writable", "value": "" },
    {"key": "Starting_Value", "value": "" },
    {"key": "Type", "value": "" },
    {"key": "Notes", "value": "" }
] ]);

var vendorTable = {
    "0": "ASHRAE",
    "1": "NIST",
    "2": "The Trane Company",
    "3": "McQuay International",
    "4": "PolarSoft",
    "5": "Johnson Controls, Inc.",
    "6": "American Auto-Matrix",
    "7": "Siemens Schweiz AG (Formerly: Landis & Staefa Division Europe)",
    "8": "Delta Controls",
    "9": "Siemens Schweiz AG",
    "10": "Schneider Electric",
    "11": "TAC",
    "12": "Orion Analysis Corporation",
    "13": "Teletrol Systems Inc.",
    "14": "Cimetrics Technology",
    "15": "Cornell University",
    "16": "United Technologies Carrier",
    "17": "Honeywell Inc.",
    "18": "Alerton / Honeywell",
    "19": "TAC AB",
    "20": "Hewlett-Packard Company",
    "21": "Dorsette’s Inc.",
    "22": "Siemens Schweiz AG (Formerly: Cerberus AG)",
    "23": "York Controls Group",
    "24": "Automated Logic Corporation",
    "25": "CSI Control Systems International",
    "26": "Phoenix Controls Corporation",
    "27": "Innovex Technologies, Inc.",
    "28": "KMC Controls, Inc.",
    "29": "Xn Technologies, Inc.",
    "30": "Hyundai Information Technology Co., Ltd.",
    "31": "Tokimec Inc.",
    "32": "Simplex",
    "33": "North Building Technologies Limited",
    "34": "Notifier",
    "35": "Reliable Controls Corporation",
    "36": "Tridium Inc.",
    "37": "Sierra Monitor Corporation/FieldServer Technologies",
    "38": "Silicon Energy",
    "39": "Kieback & Peter GmbH & Co KG",
    "40": "Anacon Systems, Inc.",
    "41": "Systems Controls & Instruments, LLC",
    "42": "Acuity Brands Lighting, Inc.",
    "43": "Micropower Manufacturing",
    "44": "Matrix Controls",
    "45": "METALAIRE",
    "46": "ESS Engineering",
    "47": "Sphere Systems Pty Ltd.",
    "48": "Walker Technologies Corporation",
    "49": "H I Solutions, Inc.",
    "50": "MBS GmbH",
    "51": "SAMSON AG",
    "52": "Badger Meter Inc.",
    "53": "DAIKIN Industries Ltd.",
    "54": "NARA Controls Inc.",
    "55": "Mammoth Inc.",
    "56": "Liebert Corporation",
    "57": "SEMCO Incorporated",
    "58": "Air Monitor Corporation",
    "59": "TRIATEK, LLC",
    "60": "NexLight",
    "61": "Multistack",
    "62": "TSI Incorporated",
    "63": "Weather-Rite, Inc.",
    "64": "Dunham-Bush",
    "65": "Reliance Electric",
    "66": "LCS Inc.",
    "67": "Regulator Australia PTY Ltd.",
    "68": "Touch-Plate Lighting Controls",
    "69": "Amann GmbH",
    "70": "RLE Technologies",
    "71": "Cardkey Systems",
    "72": "SECOM Co., Ltd.",
    "73": "ABB Gebäudetechnik AG Bereich NetServ",
    "74": "KNX Association cvba",
    "75": "Institute of Electrical Installation Engineers of Japan (IEIEJ)",
    "76": "Nohmi Bosai, Ltd.",
    "77": "Carel S.p.A.",
    "78": "UTC Fire & Security España, S.L.",
    "79": "Hochiki Corporation",
    "80": "Fr. Sauter AG",
    "81": "Matsushita Electric Works, Ltd.",
    "82": "Mitsubishi Electric Corporation, Inazawa Works",
    "83": "Mitsubishi Heavy Industries, Ltd.",
    "84": "Xylem, Inc.",
    "85": "Yamatake Building Systems Co., Ltd.",
    "86": "The Watt Stopper, Inc.",
    "87": "Aichi Tokei Denki Co., Ltd.",
    "88": "Activation Technologies, LLC",
    "89": "Saia-Burgess Controls, Ltd.",
    "90": "Hitachi, Ltd.",
    "91": "Novar Corp./Trend Control Systems Ltd.",
    "92": "Mitsubishi Electric Lighting Corporation",
    "93": "Argus Control Systems, Ltd.",
    "94": "Kyuki Corporation",
    "95": "Richards-Zeta Building Intelligence, Inc.",
    "96": "Scientech R&D, Inc.",
    "97": "VCI Controls, Inc.",
    "98": "Toshiba Corporation",
    "99": "Mitsubishi Electric Corporation Air Conditioning & Refrigeration Systems Works",
    "100": "Custom Mechanical Equipment, LLC",
    "101": "ClimateMaster",
    "102": "ICP Panel-Tec, Inc.",
    "103": "D-Tek Controls",
    "104": "NEC Engineering, Ltd.",
    "105": "PRIVA BV",
    "106": "Meidensha Corporation",
    "107": "JCI Systems Integration Services",
    "108": "Freedom Corporation",
    "109": "Neuberger Gebäudeautomation GmbH",
    "110": "eZi Controls",
    "111": "Leviton Manufacturing",
    "112": "Fujitsu Limited",
    "113": "Emerson Network Power",
    "114": "S. A. Armstrong, Ltd.",
    "115": "Visonet AG",
    "116": "M&M Systems, Inc.",
    "117": "Custom Software Engineering",
    "118": "Nittan Company, Limited",
    "119": "Elutions Inc. (Wizcon Systems SAS)",
    "120": "Pacom Systems Pty., Ltd.",
    "121": "Unico, Inc.",
    "122": "Ebtron, Inc.",
    "123": "Scada Engine",
    "124": "AC Technology Corporation",
    "125": "Eagle Technology",
    "126": "Data Aire, Inc.",
    "127": "ABB, Inc.",
    "128": "Transbit Sp. z o. o.",
    "129": "Toshiba Carrier Corporation",
    "130": "Shenzhen Junzhi Hi-Tech Co., Ltd.",
    "131": "Tokai Soft",
    "132": "Blue Ridge Technologies",
    "133": "Veris Industries",
    "134": "Centaurus Prime",
    "135": "Sand Network Systems",
    "136": "Regulvar, Inc.",
    "137": "AFDtek Division of Fastek International Inc.",
    "138": "PowerCold Comfort Air Solutions, Inc.",
    "139": "I Controls",
    "140": "Viconics Electronics, Inc.",
    "141": "Yaskawa America, Inc.",
    "142": "DEOS control systems GmbH",
    "143": "Digitale Mess- und Steuersysteme AG",
    "144": "Fujitsu General Limited",
    "145": "Project Engineering S.r.l.",
    "146": "Sanyo Electric Co., Ltd.",
    "147": "Integrated Information Systems, Inc.",
    "148": "Temco Controls, Ltd.",
    "149": "Airtek International Inc.",
    "150": "Advantech Corporation",
    "151": "Titan Products, Ltd.",
    "152": "Regel Partners",
    "153": "National Environmental Product",
    "154": "Unitec Corporation",
    "155": "Kanden Engineering Company",
    "156": "Messner Gebäudetechnik GmbH",
    "157": "Integrated.CH",
    "158": "Price Industries",
    "159": "SE-Elektronic GmbH",
    "160": "Rockwell Automation",
    "161": "Enflex Corp.",
    "162": "ASI Controls",
    "163": "SysMik GmbH Dresden",
    "164": "HSC Regelungstechnik GmbH",
    "165": "Smart Temp Australia Pty. Ltd.",
    "166": "Cooper Controls",
    "167": "Duksan Mecasys Co., Ltd.",
    "168": "Fuji IT Co., Ltd.",
    "169": "Vacon Plc",
    "170": "Leader Controls",
    "171": "Cylon Controls, Ltd.",
    "172": "Compas",
    "173": "Mitsubishi Electric Building Techno-Service Co., Ltd.",
    "174": "Building Control Integrators",
    "175": "ITG Worldwide (M) Sdn Bhd",
    "176": "Lutron Electronics Co., Inc.",
    "177": "Cooper-Atkins Corporation",
    "178": "LOYTEC Electronics GmbH",
    "179": "ProLon",
    "180": "Mega Controls Limited",
    "181": "Micro Control Systems, Inc.",
    "182": "Kiyon, Inc.",
    "183": "Dust Networks",
    "184": "Advanced Building Automation Systems",
    "185": "Hermos AG",
    "186": "CEZIM",
    "187": "Softing",
    "188": "Lynxspring, Inc.",
    "189": "Schneider Toshiba Inverter Europe",
    "190": "Danfoss Drives A/S",
    "191": "Eaton Corporation",
    "192": "Matyca S.A.",
    "193": "Botech AB",
    "194": "Noveo, Inc.",
    "195": "AMEV",
    "196": "Yokogawa Electric Corporation",
    "197": "GFR Gesellschaft für Regelungstechnik",
    "198": "Exact Logic",
    "199": "Mass Electronics Pty Ltd dba Innotech Control Systems Australia",
    "200": "Kandenko Co., Ltd.",
    "201": "DTF, Daten-Technik Fries",
    "202": "Klimasoft, Ltd.",
    "203": "Toshiba Schneider Inverter Corporation",
    "204": "Control Applications, Ltd.",
    "205": "KDT Systems Co., Ltd.",
    "206": "Onicon Incorporated",
    "207": "Automation Displays, Inc.",
    "208": "Control Solutions, Inc.",
    "209": "Remsdaq Limited",
    "210": "NTT Facilities, Inc.",
    "211": "VIPA GmbH",
    "212": "TSC21 Association of Japan",
    "213": "Strato Automation",
    "214": "HRW Limited",
    "215": "Lighting Control & Design, Inc.",
    "216": "Mercy Electronic and Electrical Industries",
    "217": "Samsung SDS Co., Ltd",
    "218": "Impact Facility Solutions, Inc.",
    "219": "Aircuity",
    "220": "Control Techniques, Ltd.",
    "221": "OpenGeneral Pty., Ltd.",
    "222": "WAGO Kontakttechnik GmbH & Co. KG",
    "223": "Cerus Industrial",
    "224": "Chloride Power Protection Company",
    "225": "Computrols, Inc.",
    "226": "Phoenix Contact GmbH & Co. KG",
    "227": "Grundfos Management A/S",
    "228": "Ridder Drive Systems",
    "229": "Soft Device SDN BHD",
    "230": "Integrated Control Technology Limited",
    "231": "AIRxpert Systems, Inc.",
    "232": "Microtrol Limited",
    "233": "Red Lion Controls",
    "234": "Digital Electronics Corporation",
    "235": "Ennovatis GmbH",
    "236": "Serotonin Software Technologies, Inc.",
    "237": "LS Industrial Systems Co., Ltd.",
    "238": "Square D Company",
    "239": "S Squared Innovations, Inc.",
    "240": "Aricent Ltd.",
    "241": "EtherMetrics, LLC",
    "242": "Industrial Control Communications, Inc.",
    "243": "Paragon Controls, Inc.",
    "244": "A. O. Smith Corporation",
    "245": "Contemporary Control Systems, Inc.",
    "246": "Intesis Software SL",
    "247": "Ingenieurgesellschaft N. Hartleb mbH",
    "248": "Heat-Timer Corporation",
    "249": "Ingrasys Technology, Inc.",
    "250": "Costerm Building Automation",
    "251": "WILO SE",
    "252": "Embedia Technologies Corp.",
    "253": "Technilog",
    "254": "HR Controls Ltd. & Co. KG",
    "255": "Lennox International, Inc.",
    "256": "RK-Tec Rauchklappen-Steuerungssysteme GmbH & Co. KG",
    "257": "Thermomax, Ltd.",
    "258": "ELCON Electronic Control, Ltd.",
    "259": "Larmia Control AB",
    "260": "BACnet Stack at SourceForge",
    "261": "G4S Security Services A/S",
    "262": "Exor International S.p.A.",
    "263": "Cristal Controles",
    "264": "Regin AB",
    "265": "Dimension Software, Inc.",
    "266": "SynapSense Corporation",
    "267": "Beijing Nantree Electronic Co., Ltd.",
    "268": "Camus Hydronics Ltd.",
    "269": "Kawasaki Heavy Industries, Ltd.",
    "270": "Critical Environment Technologies",
    "271": "ILSHIN IBS Co., Ltd.",
    "272": "ELESTA Energy Control AG",
    "273": "KROPMAN Installatietechniek",
    "274": "Baldor Electric Company",
    "275": "INGA mbH",
    "276": "GE Consumer & Industrial",
    "277": "Functional Devices, Inc.",
    "278": "ESAC",
    "279": "M-System Co., Ltd.",
    "280": "Yokota Co., Ltd.",
    "281": "Hitranse Technology Co., LTD",
    "282": "Vigilent Corporation",
    "283": "Kele, Inc.",
    "284": "Opera Electronics, Inc.",
    "285": "Gentec",
    "286": "Embedded Science Labs, LLC",
    "287": "Parker Hannifin Corporation",
    "288": "MaCaPS International Limited",
    "289": "Link4 Corporation",
    "290": "Romutec Steuer-u. Regelsysteme GmbH",
    "291": "Pribusin, Inc.",
    "292": "Advantage Controls",
    "293": "Critical Room Control",
    "294": "LEGRAND",
    "295": "Tongdy Control Technology Co., Ltd.",
    "296": "ISSARO Integrierte Systemtechnik",
    "297": "Pro-Dev Industries",
    "298": "DRI-STEEM",
    "299": "Creative Electronic GmbH",
    "300": "Swegon AB",
    "301": "Jan Brachacek",
    "302": "Hitachi Appliances, Inc.",
    "303": "Real Time Automation, Inc.",
    "304": "ITEC Hankyu-Hanshin Co.",
    "305": "Cyrus E&M Engineering Co., Ltd.",
    "306": "Badger Meter",
    "307": "Cirrascale Corporation",
    "308": "Elesta GmbH Building Automation",
    "309": "Securiton",
    "310": "OSlsoft, Inc.",
    "311": "Hanazeder Electronic GmbH",
    "312": "Honeywell Security Deutschland, Novar GmbH",
    "313": "Siemens Industry, Inc.",
    "314": "ETM Professional Control GmbH",
    "315": "Meitav-tec, Ltd.",
    "316": "Janitza Electronics GmbH",
    "317": "MKS Nordhausen",
    "318": "De Gier Drive Systems B.V.",
    "319": "Cypress Envirosystems",
    "320": "SMARTron s.r.o.",
    "321": "Verari Systems, Inc.",
    "322": "K-W Electronic Service, Inc.",
    "323": "ALFA-SMART Energy Management",
    "324": "Telkonet, Inc.",
    "325": "Securiton GmbH",
    "326": "Cemtrex, Inc.",
    "327": "Performance Technologies, Inc.",
    "328": "Xtralis (Aust) Pty Ltd",
    "329": "TROX GmbH",
    "330": "Beijing Hysine Technology Co., Ltd",
    "331": "RCK Controls, Inc.",
    "332": "Distech Controls SAS",
    "333": "Novar/Honeywell",
    "334": "The S4 Group, Inc.",
    "335": "Schneider Electric",
    "336": "LHA Systems",
    "337": "GHM engineering Group, Inc.",
    "338": "Cllimalux S.A.",
    "339": "VAISALA Oyj",
    "340": "COMPLEX (Beijing) Technology, Co., LTD.",
    "341": "SCADAmetrics",
    "342": "POWERPEG NSI Limited",
    "343": "BACnet Interoperability Testing Services, Inc.",
    "344": "Teco a.s.",
    "345": "Plexus Technology, Inc.",
    "346": "Energy Focus, Inc.",
    "347": "Powersmiths International Corp.",
    "348": "Nichibei Co., Ltd.",
    "349": "HKC Technology Ltd.",
    "350": "Ovation Networks, Inc.",
    "351": "Setra Systems",
    "352": "AVG Automation",
    "353": "ZXC Ltd.",
    "354": "Byte Sphere",
    "355": "Generiton Co., Ltd.",
    "356": "Holter Regelarmaturen GmbH & Co. KG",
    "357": "Bedford Instruments, LLC",
    "358": "Standair Inc.",
    "359": "WEG Automation - R&D",
    "360": "Prolon Control Systems ApS",
    "361": "Inneasoft",
    "362": "ConneXSoft GmbH",
    "363": "CEAG Notlichtsysteme GmbH",
    "364": "Distech Controls Inc.",
    "365": "Industrial Technology Research Institute",
    "366": "ICONICS, Inc.",
    "367": "IQ Controls s.c.",
    "368": "OJ Electronics A/S",
    "369": "Rolbit Ltd.",
    "370": "Synapsys Solutions Ltd.",
    "371": "ACME Engineering Prod. Ltd.",
    "372": "Zener Electric Pty, Ltd.",
    "373": "Selectronix, Inc.",
    "374": "Gorbet & Banerjee, LLC.",
    "375": "IME",
    "376": "Stephen H. Dawson Computer Service",
    "377": "Accutrol, LLC",
    "378": "Schneider Elektronik GmbH",
    "379": "Alpha-Inno Tec GmbH",
    "380": "ADMMicro, Inc.",
    "381": "Greystone Energy Systems, Inc.",
    "382": "CAP Technologie",
    "383": "KeRo Systems",
    "384": "Domat Control System s.r.o.",
    "385": "Efektronics Pty. Ltd.",
    "386": "Hekatron Vertriebs GmbH",
    "387": "Securiton AG",
    "388": "Carlo Gavazzi Controls SpA",
    "389": "Chipkin Automation Systems",
    "390": "Savant Systems, LLC",
    "391": "Simmtronic Lighting Controls",
    "392": "Abelko Innovation AB",
    "393": "Seresco Technologies Inc.",
    "394": "IT Watchdogs",
    "395": "Automation Assist Japan Corp.",
    "396": "Thermokon Sensortechnik GmbH",
    "397": "EGauge Systems, LLC",
    "398": "Quantum Automation (ASIA) PTE, Ltd.",
    "399": "Toshiba Lighting & Technology Corp.",
    "400": "SPIN Engenharia de Automação Ltda.",
    "401": "Logistics Systems & Software Services India PVT. Ltd.",
    "402": "Delta Controls Integration Products",
    "403": "Focus Media",
    "404": "LUMEnergi Inc.",
    "405": "Kara Systems",
    "406": "RF Code, Inc.",
    "407": "Fatek Automation Corp.",
    "408": "JANDA Software Company, LLC",
    "409": "Open System Solutions Limited",
    "410": "Intelec Systems PTY Ltd.",
    "411": "Ecolodgix, LLC",
    "412": "Douglas Lighting Controls",
    "413": "iSAtech GmbH",
    "414": "AREAL",
    "415": "Beckhoff Automation GmbH",
    "416": "IPAS GmbH",
    "417": "KE2 Therm Solutions",
    "418": "Base2Products",
    "419": "DTL Controls, LLC",
    "420": "INNCOM International, Inc.",
    "421": "BTR Netcom GmbH",
    "422": "Greentrol Automation, Inc",
    "423": "BELIMO Automation AG",
    "424": "Samsung Heavy Industries Co, Ltd",
    "425": "Triacta Power Technologies, Inc.",
    "426": "Globestar Systems",
    "427": "MLB Advanced Media, LP",
    "428": "SWG Stuckmann Wirtschaftliche Gebäudesysteme GmbH",
    "429": "SensorSwitch",
    "430": "Multitek Power Limited",
    "431": "Aquametro AG",
    "432": "LG Electronics Inc.",
    "433": "Electronic Theatre Controls, Inc.",
    "434": "Mitsubishi Electric Corporation Nagoya Works",
    "435": "Delta Electronics, Inc.",
    "436": "Elma Kurtalj, Ltd.",
    "437": "ADT Fire and Security Sp. A.o.o.",
    "438": "Nedap Security Management",
    "439": "ESC Automation Inc.",
    "440": "DSP4YOU Ltd.",
    "441": "GE Sensing and Inspection Technologies",
    "442": "Embedded Systems SIA",
    "443": "BEFEGA GmbH",
    "444": "Baseline Inc.",
    "445": "M2M Systems Integrators",
    "446": "OEMCtrl",
    "447": "Clarkson Controls Limited",
    "448": "Rogerwell Control System Limited",
    "449": "SCL Elements",
    "450": "Hitachi Ltd.",
    "451": "Newron System SA",
    "452": "BEVECO Gebouwautomatisering BV",
    "453": "Streamside Solutions",
    "454": "Yellowstone Soft",
    "455": "Oztech Intelligent Systems Pty Ltd.",
    "456": "Novelan GmbH",
    "457": "Flexim Americas Corporation",
    "458": "ICP DAS Co., Ltd.",
    "459": "CARMA Industries Inc.",
    "460": "Log-One Ltd.",
    "461": "TECO Electric & Machinery Co., Ltd.",
    "462": "ConnectEx, Inc.",
    "463": "Turbo DDC Südwest",
    "464": "Quatrosense Environmental Ltd.",
    "465": "Fifth Light Technology Ltd.",
    "466": "Scientific Solutions, Ltd.",
    "467": "Controller Area Network Solutions (M) Sdn Bhd",
    "468": "RESOL - Elektronische Regelungen GmbH",
    "469": "RPBUS LLC",
    "470": "BRS Sistemas Eletronicos",
    "471": "WindowMaster A/S",
    "472": "Sunlux Technologies Ltd.",
    "473": "Measurlogic",
    "474": "Frimat GmbH",
    "475": "Spirax Sarco",
    "476": "Luxtron",
    "477": "Raypak Inc",
    "478": "Air Monitor Corporation",
    "479": "Regler Och Webbteknik Sverige (ROWS)",
    "480": "Intelligent Lighting Controls Inc.",
    "481": "Sanyo Electric Industry Co., Ltd",
    "482": "E-Mon Energy Monitoring Products",
    "483": "Digital Control Systems",
    "484": "ATI Airtest Technologies, Inc.",
    "485": "SCS SA",
    "486": "HMS Industrial Networks AB",
    "487": "Shenzhen Universal Intellisys Co Ltd",
    "488": "EK Intellisys Sdn Bhd",
    "489": "SysCom",
    "490": "Firecom, Inc.",
    "491": "ESA Elektroschaltanlagen Grimma GmbH",
    "492": "Kumahira Co Ltd",
    "493": "Hotraco",
    "494": "SABO Elektronik GmbH",
    "495": "Equip'Trans",
    "496": "TCS Basys Controls",
    "497": "FlowCon International A/S",
    "498": "ThyssenKrupp Elevator Americas",
    "499": "Abatement Technologies",
    "500": "Continental Control Systems, LLC",
    "501": "WISAG Automatisierungstechnik GmbH & Co KG",
    "502": "EasyIO",
    "503": "EAP-Electric GmbH",
    "504": "Hardmeier",
    "505": "Mircom Group of Companies",
    "506": "Quest Controls",
    "507": "Mestek, Inc",
    "508": "Pulse Energy",
    "509": "Tachikawa Corporation",
    "510": "University of Nebraska-Lincoln",
    "511": "Redwood Systems",
    "512": "PASStec Industrie-Elektronik GmbH",
    "513": "NgEK, Inc.",
    "514": "t-mac Technologies",
    "515": "Jireh Energy Tech Co., Ltd.",
    "516": "Enlighted Inc.",
    "517": "El-Piast Sp. Z o.o",
    "518": "NetxAutomation Software GmbH",
    "519": "Invertek Drives",
    "520": "Deutschmann Automation GmbH & Co. KG",
    "521": "EMU Electronic AG",
    "522": "Phaedrus Limited",
    "523": "Sigmatek GmbH & Co KG",
    "524": "Marlin Controls",
    "525": "Circutor, SA",
    "526": "UTC Fire & Security",
    "527": "DENT Instruments, Inc.",
    "528": "FHP Manufacturing Company - Bosch Group",
    "529": "GE Intelligent Platforms",
    "530": "Inner Range Pty Ltd",
    "531": "GLAS Energy Technology",
    "532": "MSR-Electronic-GmbH",
    "533": "Energy Control Systems, Inc.",
    "534": "EMT Controls",
    "535": "Daintree Networks Inc.",
    "536": "EURO ICC d.o.o",
    "537": "TE Connectivity Energy",
    "538": "GEZE GmbH",
    "539": "NEC Corporation",
    "540": "Ho Cheung International Company Limited",
    "541": "Sharp Manufacturing Systems Corporation",
    "542": "DOT CONTROLS a.s.",
    "543": "BeaconMedæs",
    "544": "Midea Commercial Aircon",
    "545": "WattMaster Controls",
    "546": "Kamstrup A/S",
    "547": "CA Computer Automation GmbH",
    "548": "Laars Heating Systems Company",
    "549": "Hitachi Systems, Ltd.",
    "550": "Fushan AKE Electronic Engineering Co., Ltd.",
    "551": "Toshiba International Corporation",
    "552": "Starman Systems, LLC",
    "553": "Samsung Techwin Co., Ltd.",
    "554": "ISAS-Integrated Switchgear and Systems P/L",
    "555": "Reserved for ASHRAE",
    "556": "Obvius",
    "557": "Marek Guzik",
    "558": "Vortek Instruments, LLC",
    "559": "Universal Lighting Technologies",
    "560": "Myers Power Products, Inc.",
    "561": "Vector Controls GmbH",
    "562": "Crestron Electronics, Inc.",
    "563": "A&E Controls Limited",
    "564": "Projektomontaza A.D.",
    "565": "Freeaire Refrigeration",
    "566": "Aqua Cooler Pty Limited",
    "567": "Basic Controls",
    "568": "GE Measurement and Control Solutions Advanced Sensors",
    "569": "EQUAL Networks",
    "570": "Millennial Net",
    "571": "APLI Ltd",
    "572": "Electro Industries/GaugeTech",
    "573": "SangMyung University",
    "574": "Coppertree Analytics, Inc.",
    "575": "CoreNetiX GmbH",
    "576": "Acutherm",
    "577": "Dr. Riedel Automatisierungstechnik GmbH",
    "578": "Shina System Co., Ltd",
    "579": "Iqapertus",
    "580": "PSE Technology",
    "581": "BA Systems",
    "582": "BTICINO",
    "583": "Monico, Inc.",
    "584": "iCue",
    "585": "tekmar Control Systems Ltd.",
    "586": "Control Technology Corporation",
    "587": "GFAE GmbH",
    "588": "BeKa Software GmbH",
    "589": "Isoil Industria SpA",
    "590": "Home Systems Consulting SpA",
    "591": "Socomec",
    "592": "Everex Communications, Inc.",
    "593": "Ceiec Electric Technology",
    "594": "Atrila GmbH",
    "595": "WingTechs",
    "596": "Shenzhen Mek Intellisys Pte Ltd.",
    "597": "Nestfield Co., Ltd.",
    "598": "Swissphone Telecom AG",
    "599": "PNTECH JSC",
    "600": "Horner APG, LLC",
    "601": "PVI Industries, LLC",
    "602": "Ela-compil",
    "603": "Pegasus Automation International LLC",
    "604": "Wight Electronic Services Ltd.",
    "605": "Marcom",
    "606": "Exhausto A/S",
    "607": "Dwyer Instruments, Inc.",
    "608": "Link GmbH",
    "609": "Oppermann Regelgerate GmbH",
    "610": "NuAire, Inc.",
    "611": "Nortec Humidity, Inc.",
    "612": "Bigwood Systems, Inc.",
    "613": "Enbala Power Networks",
    "614": "Inter Energy Co., Ltd.",
    "615": "ETC",
    "616": "COMELEC S.A.R.L",
    "617": "Pythia Technologies",
    "618": "TrendPoint Systems, Inc.",
    "619": "AWEX",
    "620": "Eurevia",
    "621": "Kongsberg E-lon AS",
    "622": "FlaktWoods",
    "623": "E + E Elektronik GES M.B.H.",
    "624": "ARC Informatique",
    "625": "SKIDATA AG",
    "626": "WSW Solutions",
    "627": "Trefon Electronic GmbH",
    "628": "Dongseo System",
    "629": "Kanontec Intelligence Technology Co., Ltd.",
    "630": "EVCO S.p.A.",
    "631": "Accuenergy (CANADA) Inc.",
    "632": "SoftDEL",
    "633": "Orion Energy Systems, Inc.",
    "634": "Roboticsware",
    "635": "DOMIQ Sp. z o.o.",
    "636": "Solidyne",
    "637": "Elecsys Corporation",
    "638": "Conditionaire International Pty. Limited",
    "639": "Quebec, Inc.",
    "640": "Homerun Holdings",
    "641": "Murata Americas",
    "642": "Comptek",
    "643": "Westco Systems, Inc.",
    "644": "Advancis Software & Services GmbH",
    "645": "Intergrid, LLC",
    "646": "Markerr Controls, Inc.",
    "647": "Toshiba Elevator and Building Systems Corporation",
    "648": "Spectrum Controls, Inc.",
    "649": "Mkservice",
    "650": "Fox Thermal Instruments",
    "651": "SyxthSense Ltd",
    "652": "DUHA System S R.O.",
    "653": "NIBE",
    "654": "Melink Corporation",
    "655": "Fritz-Haber-Institut",
    "656": "MTU Onsite Energy GmbH, Gas Power Systems",
    "657": "Omega Engineering, Inc.",
    "658": "Avelon",
    "659": "Ywire Technologies, Inc.",
    "660": "M.R. Engineering Co., Ltd.",
    "661": "Lochinvar, LLC",
    "662": "Sontay Limited",
    "663": "GRUPA Slawomir Chelminski",
    "664": "Arch Meter Corporation",
    "665": "Senva, Inc.",
    "666": "Reserved for ASHRAE",
    "667": "FM-Tec",
    "668": "Systems Specialists, Inc.",
    "669": "SenseAir",
    "670": "AB IndustrieTechnik Srl",
    "671": "Cortland Research, LLC",
    "672": "MediaView",
    "673": "VDA Elettronica",
    "674": "CSS, Inc.",
    "675": "Tek-Air Systems, Inc.",
    "676": "ICDT",
    "677": "The Armstrong Monitoring Corporation",
    "678": "DIXELL S.r.l",
    "679": "Lead System, Inc.",
    "680": "ISM EuroCenter S.A.",
    "681": "TDIS",
    "682": "Trade FIDES",
    "683": "Knürr GmbH (Emerson Network Power)",
    "684": "Resource Data Management",
    "685": "Abies Technology, Inc.",
    "686": "Amalva",
    "687": "MIRAE Electrical Mfg. Co., Ltd.",
    "688": "HunterDouglas Architectural Projects Scandinavia ApS",
    "689": "RUNPAQ Group Co., Ltd",
    "690": "Unicard SA",
    "691": "IE Technologies",
    "692": "Ruskin Manufacturing",
    "693": "Calon Associates Limited",
    "694": "Contec Co., Ltd.",
    "695": "iT GmbH",
    "696": "Autani Corporation",
    "697": "Christian Fortin",
    "698": "HDL",
    "699": "IPID Sp. Z.O.O Limited",
    "700": "Fuji Electric Co., Ltd",
    "701": "View, Inc.",
    "702": "Samsung S1 Corporation",
    "703": "New Lift",
    "704": "VRT Systems",
    "705": "Motion Control Engineering, Inc.",
    "706": "Weiss Klimatechnik GmbH",
    "707": "Elkon",
    "708": "Eliwell Controls S.r.l.",
    "709": "Japan Computer Technos Corp",
    "710": "Rational Network ehf",
    "711": "Magnum Energy Solutions, LLC",
    "712": "MelRok",
    "713": "VAE Group",
    "714": "LGCNS",
    "715": "Berghof Automationstechnik GmbH",
    "716": "Quark Communications, Inc.",
    "717": "Sontex",
    "718": "mivune AG",
    "719": "Panduit",
    "720": "Smart Controls, LLC",
    "721": "Compu-Aire, Inc.",
    "722": "Sierra",
    "723": "ProtoSense Technologies",
    "724": "Eltrac Technologies Pvt Ltd",
    "725": "Bektas Invisible Controls GmbH",
    "726": "Entelec",
    "727": "INNEXIV",
    "728": "Covenant",
    "729": "Davitor AB",
    "730": "TongFang Technovator",
    "731": "Building Robotics, Inc.",
    "732": "HSS-MSR UG",
    "733": "FramTack LLC",
    "734": "B. L. Acoustics, Ltd.",
    "735": "Traxxon Rock Drills, Ltd",
    "736": "Franke",
    "737": "Wurm GmbH & Co",
    "738": "AddENERGIE",
    "739": "Mirle Automation Corporation",
    "740": "Ibis Networks",
    "741": "ID-KARTA s.r.o.",
    "742": "Anaren, Inc.",
    "743": "Span, Incorporated",
    "744": "Bosch Thermotechnology Corp",
    "745": "DRC Technology S.A.",
    "746": "Shanghai Energy Building Technology Co, Ltd",
    "747": "Fraport AG",
    "748": "Flowgroup",
    "749": "Skytron Energy, GmbH",
    "750": "ALTEL Wicha, Golda Sp. J.",
    "751": "Drupal",
    "752": "Axiomatic Technology, Ltd",
    "753": "Bohnke + Partner",
    "754": "Function 1",
    "755": "Optergy Pty, Ltd",
    "756": "LSI Virticus",
    "757": "Konzeptpark GmbH",
    "758": "Hubbell Building Automation, Inc.",
    "759": "eCurv, Inc.",
    "760": "Agnosys GmbH",
    "761": "Shanghai Sunfull Automation Co., LTD",
    "762": "Kurz Instruments, Inc.",
    "763": "Cias Elettronica S.r.l.",
    "764": "Multiaqua, Inc.",
    "765": "BlueBox",
    "766": "Sensidyne",
    "767": "Viessmann Elektronik GmbH",
    "768": "ADFweb.com srl",
    "769": "Gaylord Industries",
    "770": "Majur Ltd.",
    "771": "Shanghai Huilin Technology Co., Ltd.",
    "772": "Exotronic",
    "773": "Safecontrol spol s.r.o.",
    "774": "Amatis",
    "775": "Universal Electric Corporation",
    "776": "iBACnet",
    "777": "Reserved for ASHRAE",
    "778": "Smartrise Engineering, Inc.",
    "779": "Miratron, Inc.",
    "780": "SmartEdge",
    "781": "Mitsubishi Electric Australia Pty Ltd",
    "782": "Triangle Research International Ptd Ltd",
    "783": "Produal Oy",
    "784": "Milestone Systems A/S",
    "785": "Trustbridge",
    "786": "Feedback Solutions",
    "787": "IES",
    "788": "GE Critical Power",
    "789": "Riptide IO",
    "790": "Messerschmitt Systems AG",
    "791": "Dezem Energy Controlling",
    "792": "MechoSystems",
    "793": "evon GmbH",
    "794": "CS Lab GmbH",
    "795": "8760 Enterprises, Inc.",
    "796": "Touche Controls",
    "797": "Ontrol Teknik Malzeme San. ve Tic. A.S.",
    "798": "Uni Control System Sp. Z o.o.",
    "799": "Weihai Ploumeter Co., Ltd",
    "800": "Elcom International Pvt. Ltd",
    "801": "Philips Lighting",
    "802": "AutomationDirect",
    "803": "Paragon Robotics",
    "804": "SMT System & Modules Technology AG",
    "805": "OS Technology Service and Trading Co., LTD",
    "806": "CMR Controls Ltd",
    "807": "Innovari, Inc.",
    "808": "ABB Control Products",
    "809": "Gesellschaft fur Gebäudeautomation mbH",
    "810": "RODI Systems Corp.",
    "811": "Nextek Power Systems",
    "812": "Creative Lighting",
    "813": "WaterFurnace International",
    "814": "Mercury Security",
    "815": "Hisense (Shandong) Air-Conditioning Co., Ltd.",
    "816": "Layered Solutions, Inc.",
    "817": "Leegood Automatic System, Inc.",
    "818": "Shanghai Restar Technology Co., Ltd.",
    "819": "Reimann Ingenieurbüro",
    "820": "LynTec",
    "821": "HTP",
    "822": "Elkor Technologies, Inc.",
    "823": "Bentrol Pty Ltd",
    "824": "Team-Control Oy",
    "825": "NextDevice, LLC",
    "826": "GLOBAL CONTROL 5 Sp. z o.o.",
    "827": "King I Electronics Co., Ltd",
    "828": "SAMDAV",
    "829": "Next Gen Industries Pvt. Ltd.",
    "830": "Entic LLC",
    "831": "ETAP",
    "832": "Moralle Electronics Limited",
    "833": "Leicom AG",
    "834": "Watts Regulator Company",
    "835": "S.C. Orbtronics S.R.L.",
    "836": "Gaussan Technologies",
    "837": "WEBfactory GmbH",
    "838": "Ocean Controls",
    "839": "Messana Air-Ray Conditioning s.r.l.",
    "840": "Hangzhou BATOWN Technology Co. Ltd.",
    "841": "Reasonable Controls",
    "842": "Servisys, Inc.",
    "843": "halstrup-walcher GmbH",
    "844": "SWG Automation Fuzhou Limited",
    "845": "KSB Aktiengesellschaft",
    "846": "Hybryd Sp. z o.o.",
    "847": "Helvatron AG",
    "848": "Oderon Sp. Z.O.O.",
    "849": "miko",
    "850": "Exodraft",
    "851": "Hochhuth GmbH",
    "852": "Integrated System Technologies Ltd.",
    "853": "Shanghai Cellcons Controls Co., Ltd",
    "854": "Emme Controls, LLC",
    "855": "Field Diagnostic Services, Inc.",
    "856": "Ges Teknik A.S.",
    "857": "Global Power Products, Inc.",
    "858": "Option NV",
    "859": "BV-Control AG",
    "860": "Sigren Engineering AG",
    "861": "Shanghai Jaltone Technology Co., Ltd.",
    "862": "MaxLine Solutions Ltd",
    "863": "Kron Instrumentos Elétricos Ltda",
    "864": "Thermo Matrix",
    "865": "Infinite Automation Systems, Inc.",
    "866": "Vantage",
    "867": "Elecon Measurements Pvt Ltd",
    "868": "TBA",
    "869": "Carnes Company",
    "870": "Harman Professional",
    "871": "Nenutec Asia Pacific Pte Ltd",
    "872": "Gia NV",
    "873": "Kepware Tehnologies",
    "874": "Temperature Electronics Ltd",
    "875": "Packet Power",
    "876": "Project Haystack Corporation",
    "877": "DEOS Controls Americas Inc.",
    "878": "Senseware Inc",
    "879": "MST Systemtechnik AG",
    "880": "Lonix Ltd",
    "881": "GMC-I Messtechnik GmbH",
    "882": "Aviosys International Inc.",
    "883": "Efficient Building Automation Corp.",
    "884": "Accutron Instruments Inc.",
    "885": "Vermont Energy Control Systems LLC",
    "886": "DCC Dynamics",
    "887": "Brück Electronic GmbH",
    "888": "Reserved for ASHRAE",
    "889": "NGBS Hungary Ltd.",
    "890": "ILLUM Technology, LLC",
    "891": "Delta Controls Germany Limited",
    "892": "S+T Service & Technique S.A.",
    "893": "SimpleSoft",
    "894": "Candi Controls, Inc.",
    "895": "EZEN Solution Inc.",
    "896": "Fujitec Co. Ltd.",
    "897": "Terralux",
    "898": "Annicom",
    "899": "Bihl+Wiedemann GmbH",
    "900": "Daper, Inc.",
    "901": "Schüco International KG",
    "902": "Otis Elevator Company",
    "903": "Fidelix Oy",
    "904": "RAM GmbH Mess- und Regeltechnik",
    "905": "WEMS",
    "906": "Ravel Electronics Pvt Ltd",
    "907": "OmniMagni",
    "908": "Echelon",
    "909": "Intellimeter Canada, Inc.",
    "910": "Bithouse Oy",
    "911": "Reserved for ASHRAE",
    "912": "BuildPulse",
    "913": "Shenzhen 1000 Building Automation Co. Ltd",
    "914": "AED Engineering GmbH",
    "915": "Güntner GmbH & Co. KG",
    "916": "KNXlogic",
    "917": "CIM Environmental Group",
    "918": "Flow Control",
    "919": "Lumen Cache, Inc.",
    "920": "Ecosystem",
    "921": "Potter Electric Signal Company, LLC",
    "922": "Tyco Fire & Security S.p.A.",
    "923": "Watanabe Electric Industry Co., Ltd.",
    "924": "Causam Energy",
    "925": "W-tec AG",
    "926": "IMI Hydronic Engineering International SA",
    "927": "ARIGO Software",
    "928": "MSA Safety",
    "929": "Smart Solucoes Ltda - MERCATO",
    "930": "PIATRA Engineering",
    "931": "ODIN Automation Systems, LLC",
    "932": "Belparts NV",
    "999": "Reserved for ASHRAE"
};


devicesStore.getPlatform = function () {
    return _platform;
};

devicesStore.getRegistryValues = function (deviceId, deviceAddress, deviceName) {

    var device = devicesStore.getDeviceRef(deviceId, deviceAddress, deviceName);
    var config = [];

    if (device)
    {
        if (device.registryConfig.length)
        {
            config = device.registryConfig;
        }
    }
    else
    {
        config = _placeHolders;
    }
    
    return config;    
};

devicesStore.getSettingsTemplate = function () {

    return (ObjectIsEmpty(_settingsTemplate) ? null : _settingsTemplate);
}

devicesStore.getSavedRegistryFiles = function () {
    return (ObjectIsEmpty(_savedRegistryFiles) ? null : _savedRegistryFiles);
};

devicesStore.getDevices = function (platform, bacnetIdentity) {

    var devices = [];

    if (typeof platform !== "undefined" && platform.hasOwnProperty("uuid"))
    {
        devices = _devices.filter(function (device) {
            return ((device.platformUuid === platform.uuid) 
                && (device.bacnetProxyIdentity === bacnetIdentity));
        });
    }

    return JSON.parse(JSON.stringify(devices));
}

devicesStore.getDevicesList = function (platformUuid) {

    return (_devicesList.hasOwnProperty(platformUuid) ? 
                JSON.parse(JSON.stringify(_devicesList[platformUuid])) : 
                    []);
}

devicesStore.getDeviceByID = function (deviceId) {

    var device = _devices.find(function (dvc) {
        return (dvc.id === deviceId);
    });

    return device;
}

devicesStore.getDeviceRef = function (deviceId, deviceAddress, deviceName) {

    var device = _devices.find(function (dvc) {
        return (
            (dvc.id === deviceId) && 
            (dvc.address === deviceAddress) && 
            (deviceName ? dvc.name === deviceName : true)
        );
    });

    return (typeof device === "undefined" ? null : device);
}

devicesStore.getDevice = function (deviceId, deviceAddress, deviceName) {

    return JSON.parse(JSON.stringify(devicesStore.getDeviceRef(deviceId, deviceAddress, deviceName)));
}

devicesStore.getNewScan = function () {

    return _newScan;
}

devicesStore.deviceHasFocus = function (deviceId, deviceAddress) {
    return (_focusedDevice.id === deviceId && _focusedDevice.address === deviceAddress);
}

devicesStore.getScanningComplete = function () {
    return (_scanningComplete);
}

devicesStore.getUpdatedRow = function (deviceId, deviceAddress) {

    var updatedRow = null;

    if (_updatedRow.hasOwnProperty("attributes"))
    {
        if (_updatedRow.deviceId === deviceId && _updatedRow.deviceAddress === deviceAddress)
        {
            updatedRow = _updatedRow.attributes.toJS(); // then converting back to Immutable 
                                            // list in component ensures it's a new object,
                                            // not using the same reference
            _updatedRow = {};
        }
    }

    return updatedRow;
}

devicesStore.enableBackupPoints = function (deviceId, deviceAddress) {
    var backup = _backupPoints.find(function (backups) {
        return backups.id === deviceId && backups.address === deviceAddress;
    });

    return (typeof backup !== "undefined");
}

devicesStore.reconfiguringDevice = function () {
    return _reconfiguringDevice;
}

devicesStore.getReconfiguration = function () {
    return _reconfiguration;
}

devicesStore.getClearConfig = function () {
    return _clearConfig;
}

devicesStore.dispatchToken = dispatcher.register(function (action) {
    dispatcher.waitFor([authorizationStore.dispatchToken]);

    _newScan = false;
    _reconfiguringDevice = false;
    _clearConfig = false;

    switch (action.type) {
        
        case ACTION_TYPES.CONFIGURE_DEVICES:
            _platform = action.platform;
            _devices = [];
            _newScan = true;
            _backupPoints = [];
            _scanningComplete = false;
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.CLEAR_CONFIG:
            _clearConfig = true;
            _reconfiguration = {};
            _devices = [];
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.LISTEN_FOR_IAMS:
            _scanningComplete = false;
            _warnings = {};
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.DEVICE_DETECTED:
            loadDevice(action.device, action.platform, action.bacnet);

            if (_devices.length)
            {
                devicesStore.emitChange();
            }
            break;
        case ACTION_TYPES.DEVICE_SCAN_FINISHED:

            _scanningComplete = true;

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.POINT_SCAN_FINISHED:

            var deviceId = action.device.id;
            var deviceAddress = action.device.address;
            var device = devicesStore.getDeviceRef(deviceId, deviceAddress);

            device.configuring = false;

            setBackupPoints(device);

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.POINT_RECEIVED:
            loadPoint(action.data);
            devicesStore.emitChange();
            break;            
        case ACTION_TYPES.FOCUS_ON_DEVICE:
            
            var focusedDevice = devicesStore.getDeviceRef(action.deviceId, action.deviceAddress);

            if (focusedDevice)
            {
                if (_focusedDevice.id !== focusedDevice.id || _focusedDevice.address !== focusedDevice.address)
                {
                    _focusedDevice.id = focusedDevice.id;
                    _focusedDevice.address = focusedDevice.address;

                    devicesStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.REFRESH_DEVICE_POINTS:

            var device = devicesStore.getDeviceRef(action.deviceId, action.deviceAddress);            

            if (device)
            {
                var backupPoints = _backupPoints.find(function (backups) {
                    return backups.id === device.id && 
                        backups.address === device.address;
                });

                if (typeof backupPoints !== "undefined")
                {
                    device.registryConfig = JSON.parse(JSON.stringify(backupPoints.points));
                    device.registryCount = device.registryCount + 1;
                    devicesStore.emitChange();
                }
            }

            break;

        case ACTION_TYPES.CONFIGURE_DEVICE:
            var device = devicesStore.getDeviceRef(action.device.id, action.device.address);

            if (device)
            {
                device.showPoints = action.device.showPoints; 
                device.configuring = action.device.configuring;
                device.configuringStarted = true;
                device.bacnetProxy = action.bacnet;

                if (device.configuring)
                {
                    device.registryCount = device.registryCount + 1;
                    device.registryConfig = [];
                }
            }

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.TOGGLE_SHOW_POINTS:
            var device = devicesStore.getDeviceRef(action.device.id, action.device.address);

            if (device)
            {
                device.showPoints = action.device.showPoints;
            }

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.CANCEL_REGISTRY:
            var device = devicesStore.getDeviceRef(action.device.id, action.device.address);

            if (device)
            {
                device.registryConfig = [];
                device.showPoints = false;
                device.configuring = false;
                device.configuringStarted = false;
            }

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.LOAD_REGISTRY:
            
            var device = devicesStore.getDeviceRef(action.deviceId, action.deviceAddress);

            if (device)
            {
                device.registryCount = device.registryCount + 1;
                device.registryConfig = getPreppedData(action.data);
                device.showPoints = true;
            }
             
            devicesStore.emitChange();
            break;

        case ACTION_TYPES.LOAD_REGISTRY_FILES:
            
            _savedRegistryFiles = {
                files: action.registryFiles,
                deviceId: action.deviceId,
                deviceAddress: action.deviceAddress
            };
             
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.UNLOAD_REGISTRY_FILES:
            
            _savedRegistryFiles = {};
             
            devicesStore.emitChange();
            break;
        case ACTION_TYPES.UPDATE_REGISTRY_ROW:
            
            var i = -1;
            var keyProps = [];

            _updatedRow = { 
                deviceId: action.deviceId,
                deviceAddress: action.deviceAddress,
                attributes: action.attributes
            };

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.RECONFIGURE_DEVICE:
            
            _reconfiguration = action.configuration;
            _reconfiguration.deviceName = action.deviceName.replace("devices/", "");

            _reconfiguration.max_per_request = _reconfiguration.driver_config.max_per_request;
            _reconfiguration.minimum_priority = _reconfiguration.driver_config.minimum_priority;

            delete _reconfiguration.driver_config.max_per_request;
            delete _reconfiguration.driver_config.minimum_priority;

            _platform = {
                "uuid": action.platformUuid
            };

            var device = {
                id: _reconfiguration.driver_config.device_id,
                address: _reconfiguration.driver_config.device_address,
                name: _reconfiguration.deviceName,
                platformUuid: action.platformUuid,
                agentDriver: action.agentDriver
            }

            reconfigureRegistry(device, _reconfiguration, action.data);

            _reconfiguringDevice = true;

            devicesStore.emitChange();
            break;
        case ACTION_TYPES.SAVE_CONFIG:
            
            _settingsTemplate = action.settings;

            break;
        case ACTION_TYPES.UPDATE_DEVICES_LIST:            
            _devicesList[action.platformUuid] = action.devices;
            break;
        default:
            break;
    }

    function setBackupPoints(device)
    {
        var backup = { 
            id: device.id, 
            address: device.address, 
            points: JSON.parse(JSON.stringify(device.registryConfig))
        };

        var index = -1;
        _backupPoints.find(function (backups, i) {
            var match = (backups.id === device.id && 
                backups.address === device.address);

            if (match)
            {
                index = i;
            }

            return match;
        });

        if (index < 0)
        {
            _backupPoints.push(backup);    
        }
        else
        {
            _backupPoints[index] = backup;
        }
    }

    function sortPointColumns(row)
    {
        var sortedPoint = [];

        var indexCell = row.find(function (cell) {
            return cell.key === "index";
        })

        if (typeof indexCell !== "undefined")
        {
            sortedPoint.push(indexCell);
        }

        var referencePointNameCell = row.find(function (cell) {
            return cell.key === "reference_point_name";
        })

        if (typeof referencePointNameCell !== "undefined")
        {
            sortedPoint.push(referencePointNameCell);
        }

        var pointNameCell = row.find(function (cell) {
            return cell.key === "point_name";
        })

        if (typeof pointNameCell !== "undefined")
        {
            sortedPoint.push(pointNameCell);
        }

        var volttronPointNameCell = row.find(function (cell) {
            return cell.key === "volttron_point_name";
        })

        if (typeof volttronPointNameCell !== "undefined")
        {
            sortedPoint.push(volttronPointNameCell);
        }

        for (var i = 0; i < row.length; ++i)
        {
            if (row[i].key !== "index" && 
                row[i].key !== "reference_point_name" && 
                row[i].key !== "point_name" && 
                row[i].key !== "volttron_point_name")
            {
                sortedPoint.push(row[i]);
            }
        }

        return sortedPoint;
    }

    function getPreppedData(data) {

        var preppedData = data.map(function (row) {
            var preppedRow = row.map(function (cell) {

                prepCell(cell);

                return cell;
            });

            var sortedRow = sortPointColumns(preppedRow);

            return sortedRow;
        });


        return preppedData;
    }

    function prepCell(cell) {

        cell.key = cell.key.toLowerCase();

        cell.editable = !(cell.key === "point_name" || 
                            cell.key === "reference_point_name" || 
                            cell.key === "object_type" || 
                            cell.key === "index");

        cell.filterable = (cell.key === "point_name" || 
                            cell.key === "reference_point_name" || 
                            cell.key === "volttron_point_name" || 
                            cell.key === "index");
    }

    function loadPoint(data) 
    {
        if (data)
        {
            var pointData = JSON.parse(data); 

            // can remove && !pointData.hasProp(device_name) if fix websocket endpoint collision
            if (pointData.hasOwnProperty("device_id") && (!pointData.hasOwnProperty("device_name")))
            {
                var deviceId = Number(pointData.device_id);
                var deviceAddress = pointData.address;
                var device = devicesStore.getDeviceRef(deviceId, deviceAddress);

                if (device)
                {
                    if (!pointData.hasOwnProperty("status"))
                    {                          
                        var newPoint = [];

                        for (var key in pointData.results)
                        {
                            var cell = {
                                key: key.toLowerCase().replace(/ /g, "_"),
                                label: key,
                                value: (pointData.results[key] === null ? "" : pointData.results[key])
                            };

                            prepCell(cell);

                            newPoint.push(cell);
                        }

                        var sortedPoint = sortPointColumns(newPoint);
                        device.registryConfig.push(sortedPoint);
                    }
                    else
                    {
                        if (pointData.status === "COMPLETE")
                        {
                            device.configuring = false;
                            setBackupPoints(device);
                        }
                    }
                }
            }
        }

        return device.configuring;
    }

    function loadDevice(device, platformUuid, bacnetIdentity) 
    {
        var deviceId = Number(device.device_id);

        _devices.push({
            id: deviceId,
            name: device.device_name,
            type: device.type,
            vendor_id: device.vendor_id,
            address: device.address,
            max_apdu_length: device.max_apdu_length,
            segmentation_supported: device.segmentation_supported,
            showPoints: false,
            configuring: false,
            platformUuid: platformUuid,
            bacnetProxyIdentity: bacnetIdentity,
            agentDriver: device.agentDriver,
            registryCount: 0,
            registryConfig: [],
            keyProps: _defaultKeyProps,
            items: [
                { key: "address", label: "Address", value: device.address },  
                { key: "deviceName", label: "Name", value: device.device_name },  
                { key: "deviceDescription", label: "Description", value: device.device_description }, 
                { key: "deviceId", label: "Device ID", value: deviceId },
                { key: "vendorId", label: "Vendor ID", value: device.vendor_id }, 
                { key: "vendor", label: "Vendor", value: vendorTable[device.vendor_id] },
                { key: "type", label: "Type", value: device.type }
            ]
        });
    }

    function reconfigureRegistry(device, configuration, data) {

        var preppedDevice = {
            id: device.id,
            address: device.address,
            name: device.name,
            platformUuid: device.platformUuid,
            agentDriver: device.agentDriver,
            registryFile: configuration.registryFile,
            showPoints: true,
            configuring: false,
            registryCount: 0,
            registryConfig: getPreppedData(data),
            keyProps: _defaultKeyProps
        };

        var index = -1;

        var deviceInList = _devices.find(function (dvc, i) {
            var match = ((dvc.id === device.id) && (dvc.address === device.address) && (dvc.name === device.name));

            if (match)
            {
                index = i;
            }

            return match;
        });

        if (index > -1)
        {
            preppedDevice.registryCount = _devices[index].registryCount + 1;

            _devices.splice(index, 1, preppedDevice);
        }
        else
        {
            _devices.push(preppedDevice);
        }
    }
    
});

function ObjectIsEmpty(obj)
{
    return Object.keys(obj).length === 0;
}

module.exports = devicesStore;