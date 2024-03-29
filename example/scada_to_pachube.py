import os
import eeml
from eeml import Unit
import datetime
import csv
import urllib, urllib2
from zipfile import ZipFile
import json

# parameters
API_KEY = 'dabe23be214ab746c97dddc1028fded3d1113b5cfdd1ca82661347df3c5e8f0c'
url_base = 'http://www.nemweb.com.au'

class AustralianDollar(Unit):
    """
    Australian Dollar unit class.
    """
    def __init__(self):
        """
        Initialize the `Unit` parameters with Celsius.
        """
        Unit.__init__(self, 'AustralianDollar', 'contextDependentUnits', 'AUD')



class ElectricityCarbonEmissionIntensity(Unit):
    """
    Carbon Emission Intensity unit class.
    """

    def __init__(self):
        """
        Initialize the `Unit` parameters with Celsius.
        """
        Unit.__init__(self, 'TonCO2EqPerMWHSentOut', 'derivedUnits', 't CO2-e / MWh sent out')



# Opening the latest forecast demand and price file, for each region
last_traded_demand_dict={}
last_traded_rrp_dict={}
current_forecast_demand_dict={}
current_forecast_rrp_dict={}


for k in ['VIC1','SA1','NSW1','TAS1','QLD1']:
	url_dandp = url_base + "/mms.GRAPHS/GRAPHS/GRAPH_30"+k+".csv"
	fn,d = urllib.urlretrieve(url_dandp)
	f = open(fn,'r')
	reader = csv.reader(f, delimiter=',', quoting=csv.QUOTE_NONE) 

	count = 0
	for row in reader:
		if len(row)>4:
			if row[4] =='PD':
				count = count + 1
				if count == 1:
					# The previous row, stored in last_row was the last TRADEd value (last actual value)
					# All values from this point on are forecasts
					last_traded_demand_dict[row[0]]=row[2]
					last_traded_rrp_dict[row[0]]=row[3]
				if count == 2:
					# This is the 3rd row, that corresponds to the forecast for the current time period
					# because of the 1 hour delay between real-price committed as traded and current time
					current_forecast_demand_dict[row[0]]=row[2]
					current_forecast_rrp_dict[row[0]]=row[3]					
			last_row = row

	f.close()

#print last_traded_demand_dict
#print last_traded_rrp_dict
#print current_forecast_demand_dict
#print current_forecast_rrp_dict

# Finding out the name of the latest file (updated every 5 minutes)
url_dir = url_base + '/REPORTS/CURRENT/Dispatch_SCADA/'
response = urllib2.urlopen(url_dir)

# Extracting the last link in the page - it's the name of the latest SCADA file
html = response.read()
ll = html.split('A HREF="')[-2]
ll2 = ll.split('"')[0]
latest_scada_zip_file = url_base+ll2
print 'Lastest SCADA file is: '+latest_scada_zip_file

# Downloading the latest SCADA file (zipped)
fn, d = urllib.urlretrieve(latest_scada_zip_file)
print 'Local copy (SCADA file) is at: '+fn

# Opening the reference file that contains static information about the generators
url_spreadsheet = 'https://docs.google.com/spreadsheet/pub?key=0Asxkb_brURPldDhhSmp2ZUNiSWZDVUlnaXFKQVNfVFE&single=true&gid=5&output=csv'
fn2, d2 = urllib.urlretrieve(url_spreadsheet)
print 'Local copy (spreadsheet) is at: '+fn2
f2 = open(fn2,'r')
reader2 = csv.reader(f2, delimiter=',', quoting=csv.QUOTE_NONE)

# Populating dictionaries for future groupings
state_dict = {}
state_dict_clean = {}
fueltype_dict = {}
fueldesc_dict = {}
fueldesc_dict_clean = {}
techtype_dict = {}
techdesc_dict = {}
gen_label_dict = {}
gen_owned_dict = {}
gen_reg_capacity_dict = {}
gen_emission_factor_dict = {}

for row in reader2:
	if reader2.line_num <2:
		continue
	if len(row)>19:
		if len(row[2])<2 or len(row[6])<2 or len(row[7])<2 or len(row[8])<2 or len(row[9])<2:
			print "Unknown characteristic(s) for "+str(row[13])
		else:
			gen_label_dict[row[13].translate(None,'#/')] = row[1]
			gen_owned_dict[row[13].translate(None,'#/')] = row[0]
			gen_reg_capacity_dict[row[13].translate(None,'#/')] = row[14]
			gen_emission_factor_dict[row[13].translate(None,'#/')] = row[19]
			state_dict[row[13]] = row[2]	
			state_dict_clean[row[13].translate(None,'#/')] = row[2]	
			fueltype_dict[row[13]] = row[6]
			fueldesc_dict[row[13]] = row[7]
			fueldesc_dict_clean[row[13].translate(None,'#/')] = row[7]
			techtype_dict[row[13]] = row[8]
			techdesc_dict[row[13]] = row[9]

f2.close()

#print state_dict

# Uncompressing and parsing the SCADA file
#with ZipFile(fn,'r') as zf:
zf = ZipFile(fn,'r')
try:
	# Listing the resources in the zip file - there is only 1
	zfnl = zf.namelist()
	print 'Filename to extract from the archive: '+ zfnl[0]
	f = zf.open(zfnl[0])
	# It's a CSV file - we only extract the relevant lines (=HAZELWOOD) 
	# and columns (dispatcher name in column 5 and quantity dispatched in column 6)
	reader = csv.reader(f, delimiter=',', quoting=csv.QUOTE_NONE)

	# Reading the file
	readings_dict = {}
	readings_state_dict = {}
	readings_renewable_dict = {}	
	readings_fuel_dict = {}	
	readings_vic_renewable_dict = {}	
	readings_vic_fuel_dict = {}	
	for row in reader:
		# First 2 rows contain headers
		if reader.line_num < 3:
			continue
		# Subsequent rows contain the information we populate the dictionary with
		if len(row)>6:
			duid = row[5]
			qty = row[6]

			# NEM total
			if readings_dict.has_key("ALL"):
				readings_dict["ALL"] = str(float(readings_dict["ALL"]) + float(qty))
			else:
				readings_dict["ALL"] = qty
			# Per station (DUID)
			readings_dict[duid.translate(None,'#/')]=qty
			# The name of the generators had to be cleaned from these 2 special characters
			# The Pachube API would not accept the request with these characters in
			
			# Building the state dictionary with accumulated quantity
			if state_dict.has_key(duid):
				a = state_dict[duid]
				# State aggregation
				if readings_state_dict.has_key(a):
					readings_state_dict[a] = str(float(readings_state_dict[a]) + float(qty))
				else:
					readings_state_dict[a] = qty

				# NEM total
				if readings_state_dict.has_key("ALL"):
					readings_state_dict["ALL"] = str(float(readings_state_dict["ALL"]) + float(qty))
				else:
					readings_state_dict["ALL"] = qty
			else:
				print 'No information available for DUID: '+str(duid)
				
			# Building the dictionary renewable / combustion with accumulated quantity
			if techtype_dict.has_key(duid):
				a = techtype_dict[duid]
				# Aggregation by technology type
				if readings_renewable_dict.has_key(a):
					readings_renewable_dict[a] = str(float(readings_renewable_dict[a]) + float(qty))
				else:
					readings_renewable_dict[a] = qty
				# all technologies
				if readings_renewable_dict.has_key("ALL"):
					readings_renewable_dict["ALL"] = str(float(readings_renewable_dict["ALL"]) + float(qty))
				else:
					readings_renewable_dict["ALL"] = qty
					
				# Aggregation by tech type in Victoria
				if state_dict[duid] == 'VIC1':
					if readings_vic_renewable_dict.has_key(a):
						readings_vic_renewable_dict[a] = str(float(readings_vic_renewable_dict[a]) + float(qty))
					else:
						readings_vic_renewable_dict[a] = qty

			# Building the dictionary fuel description with accumulated quantity
			if fueldesc_dict.has_key(duid):
				a = fueldesc_dict[duid].translate(None,'#/ ')
				# Aggregation by technology type
				if readings_fuel_dict.has_key(a):
					readings_fuel_dict[a] = str(float(readings_fuel_dict[a]) + float(qty))
				else:
					readings_fuel_dict[a] = qty
				# all fuels
				if readings_fuel_dict.has_key("ALL"):
					readings_fuel_dict["ALL"] = str(float(readings_fuel_dict["ALL"]) + float(qty))
				else:
					readings_fuel_dict["ALL"] = qty
				# Aggregation by fuel description in Victoria
				if state_dict[duid] =='VIC1':
					if readings_vic_fuel_dict.has_key(a):
						readings_vic_fuel_dict[a] = str(float(readings_vic_fuel_dict[a]) + float(qty))
					else:
						readings_vic_fuel_dict[a] = qty
finally:
	zf.close()

f.close()
# Not needed here, maybe because it's a temp file defined only during the With clause
#os.remove(fn)

#print readings_state_dict
#print readings_renewable_dict
#print readings_fuel_dict
#print readings_vic_renewable_dict
#print readings_vic_fuel_dict

# Granular update
API_URL = '/api/47944.xml'
print 'Number of generators in the SCADA file:'+str(len(readings_dict.keys()))
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, readings_dict[k], unit=eeml.Watt()) for k in readings_dict.keys()])
pac.put()

# Aggregated by state update
API_URL = '/api/48009.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, readings_state_dict[k], unit=eeml.Watt()) for k in readings_state_dict.keys()])
pac.put()

# Aggregated by combustion or renewable
API_URL = '/api/48011.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, readings_renewable_dict[k], unit=eeml.Watt()) for k in readings_renewable_dict.keys()])
#pac.put()

# Aggregated by tech type
API_URL = '/api/48012.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, readings_fuel_dict[k], unit=eeml.Watt()) for k in readings_fuel_dict.keys()])
#pac.put()

# Aggregated by combustion or renewable (VIC)
API_URL = '/api/48014.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, readings_vic_renewable_dict[k], unit=eeml.Watt()) for k in readings_vic_renewable_dict.keys()])
#pac.put()

# Aggregated by tech type (VIC)
API_URL = '/api/48013.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, readings_vic_fuel_dict[k], unit=eeml.Watt()) for k in readings_vic_fuel_dict.keys()])
#pac.put()

# Spot price (last traded), by region
API_URL = '/api/48124.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, last_traded_rrp_dict[k], unit=AustralianDollar()) for k in last_traded_rrp_dict.keys()])
#pac.put()

# Spot price (current forecast), by region
API_URL = '/api/48125.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, current_forecast_rrp_dict[k], unit=AustralianDollar()) for k in current_forecast_rrp_dict.keys()])
#pac.put()

# Demand (last traded)
# to be implemented if needed
#last_traded_demand_dict

# Demand (current forecast)
# to be implemented if needed
#current_forecast_demand_dict


# Base JSON to populate using the results of the different dictionaries
data = {"items":[{"code" : "gen","label":"Electricity generated","items":[]},{"code" : "em","label":"Carbon emissions","items":[]},{"code" : "emi","label":"Emission intensity","items":[]}]}

# readings_dict contains a dictionary of DUID => qty
# state_dict contains a dictionary of DUID => state
# fueldesc_dict contains a dictionary of DUID => fuel


state_emission_dict = {}

for d,curr_qty in readings_dict.iteritems():
	# Considering the data dic as a tree in which we have to place appropriately the leaf, and build the intermediate nodes along the way
#	print d

	if state_dict_clean.has_key(d) and float(curr_qty)>1.0:
	
		curr_s = state_dict_clean[d]
		added_to_state = False

		for m in data["items"]:
			# km of interest is 0
			km = 0
			km1 = 1
			if m["code"]=="gen":
				for s in m["items"]:
					if s["code"]==curr_s[:-1]:
						ks = m["items"].index(s)
						# The state already exists and we just add to it
						data["items"][km]["items"][ks]["qty"]=str(round(float(s["qty"])+float(curr_qty),2))
						data["items"][km1]["items"][ks]["qty"]=str(round(float(data["items"][km1]["items"][ks]["qty"])+float(curr_qty)*float(gen_emission_factor_dict[d])/12,2))
						state_emission_dict[data["items"][km1]["items"][ks]["code"]] = data["items"][km1]["items"][ks]["qty"]
						added_to_state = True
				if added_to_state == False:
					# The state was not in yet
					data["items"][km]["items"]+=[{"code":str(curr_s[:-1]),"label":str(curr_s[:-1]),"qty":str(curr_qty),"items":[]}]
					data["items"][km1]["items"]+=[{"code":str(curr_s[:-1]),"label":str(curr_s[:-1]),"qty":str(float(curr_qty)*float(gen_emission_factor_dict[d])/12),"items":[]}]
					ks = data["items"][km]["items"].index({"code":str(curr_s[:-1]),"label":str(curr_s[:-1]),"qty":str(curr_qty),"items":[]})
					state_emission_dict[data["items"][km1]["items"][ks]["code"]] = data["items"][km1]["items"][ks]["qty"]


				# Fuel
				if fueldesc_dict_clean.has_key(d):
					curr_f = fueldesc_dict_clean[d]
					added_to_fuel = False

					for f in data["items"][km]["items"][ks]["items"]:
					
						if f["code"]==curr_f:
							kf = data["items"][km]["items"][ks]["items"].index(f)
							# The qty is added to this fuel
#							print "Adding fuel '",curr_f,"' in ",curr_s," to existing array"
#							print "Before:",data["items"][km]["items"][ks]["items"]
							data["items"][km]["items"][ks]["items"][kf]["qty"]=str(round(float(f["qty"])+float(curr_qty),2))
							data["items"][km1]["items"][ks]["items"][kf]["qty"]=str(round(float(data["items"][km1]["items"][ks]["items"][kf]["qty"])+float(curr_qty)*float(gen_emission_factor_dict[d])/12,2))
#							print "After:",data["items"][km]["items"][ks]["items"]
							added_to_fuel = True
						
					if added_to_fuel == False:
						# Then we create the entry in the store
						data["items"][km]["items"][ks]["items"]+=[{"code":str(curr_f),"label":str(curr_f),"qty":str(curr_qty),"items":[]}]
						data["items"][km1]["items"][ks]["items"]+=[{"code":str(curr_f),"label":str(curr_f),"qty":str(float(curr_qty)*float(gen_emission_factor_dict[d])/12),"items":[]}]
#						print "Creating entry in fuel array '",curr_f,"' in ",curr_s
#						print "After:",data["items"][km]["items"][ks]["items"]
						kf = data["items"][km]["items"][ks]["items"].index({"code":str(curr_f),"label":str(curr_f),"qty":str(curr_qty),"items":[]})

				else:
				
					print "Key not in the fuel dictionary:",d

				# Individual generators
				# No addition here (we are at the leaf nodes)
				# We just insert the element
				data["items"][km]["items"][ks]["items"][kf]["items"] +=  [{"code":str(d),"label":str(gen_label_dict[d]),"qty":str(round(float(curr_qty),2)),"owner":str(gen_owned_dict[d]),"capacity":str(gen_reg_capacity_dict[d]),"ef":str(gen_emission_factor_dict[d]),"leaf":True}]
				data["items"][km1]["items"][ks]["items"][kf]["items"] +=  [{"code":str(d),"label":str(gen_label_dict[d]),"qty":str(round(float(curr_qty)*float(gen_emission_factor_dict[d])/12,2)),"owner":str(gen_owned_dict[d]),"capacity":str(gen_reg_capacity_dict[d]),"ef":str(gen_emission_factor_dict[d]),"leaf":True}]

	else:
		if not(state_dict_clean.has_key(d)):
			print "Key not in the state dictionary:",d
		if not(float(curr_qty)>1.0):
			print "Qty dispatched (",curr_qty,") too small for: ",d

print "Current electricity generated (MW):", readings_state_dict
print "Current carbon emission rate (t CO2-e / 5mn):",state_emission_dict

# Current carbon emissions, aggregated by state
API_URL = '/api/54179.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, state_emission_dict[k], unit=eeml.Unit('TonCO2EqPer5Mn','contextDependentUnits','t CO2-e / 5mn')) for k in state_emission_dict.keys()])
pac.put()


state_emission_intensity_dict={}

# Instead of running as many times as there are generators (and bubble them up in the structure), we need 1 entry per existing node in the final structure
for m in data["items"]:
	# km of interest is 2
	km = 0
	km1 = 1
	km2 = 2
	if m["code"]=="gen":
		for s in m["items"]:
			ks = m["items"].index(s)
			data["items"][km2]["items"]+=[{"code":data["items"][km]["items"][ks]["code"],"label":data["items"][km]["items"][ks]["label"],"qty":str(round(float(data["items"][km1]["items"][ks]["qty"])*12.0/float(data["items"][km]["items"][ks]["qty"]),2)),"items":[]}]
			state_emission_intensity_dict[m["items"][ks]["code"]] = str(round(float(data["items"][km1]["items"][ks]["qty"])*12.0/float(data["items"][km]["items"][ks]["qty"]),2))

			for f in data["items"][km]["items"][ks]["items"]:
				kf = data["items"][km]["items"][ks]["items"].index(f)
				data["items"][km2]["items"][ks]["items"]+=[{"code":data["items"][km]["items"][ks]["items"][kf]["code"],"label":data["items"][km]["items"][ks]["items"][kf]["label"],"qty":str(round(float(data["items"][km1]["items"][ks]["items"][kf]["qty"])*12.0/float(data["items"][km]["items"][ks]["items"][kf]["qty"]),2)),"items":[]}]

				for d,curr_qty in readings_dict.iteritems():
					if state_dict_clean.has_key(d) and float(curr_qty)>1.0:
						curr_s = state_dict_clean[d][:-1]
						curr_f = fueldesc_dict_clean[d]
						if curr_s == data["items"][km2]["items"][ks]["code"]  and curr_f == data["items"][km2]["items"][ks]["items"][kf]["code"]:
							data["items"][km2]["items"][ks]["items"][kf]["items"] +=  [{"code":str(d),"label":str(gen_label_dict[d]),"qty":str(gen_emission_factor_dict[d]),"owner":str(gen_owned_dict[d]),"capacity":str(gen_reg_capacity_dict[d]),"ef":str(gen_emission_factor_dict[d]),"leaf":True}]


print "Current carbon emission intensity (tCo2-e / MWh sent):",state_emission_intensity_dict

# Current carbon emissions, aggregated by state
API_URL = '/api/54177.xml'
# Transmitting the value to Pachube as an EEML object
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(k, state_emission_intensity_dict[k], unit=ElectricityCarbonEmissionIntensity()) for k in state_emission_intensity_dict.keys()])
pac.put()



# Outputting the dictionary for RTEM application
#jf = open('state_python.json','w')
jf = open('/usr/share/apache2/rtem/app/data/state.json','w')
jf.write(json.dumps(data,sort_keys=True, indent=4))
jf.close()
