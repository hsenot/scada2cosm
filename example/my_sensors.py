import eeml
import datetime

a = datetime.tzinfo()

# parameters
API_KEY = 'dabe23be214ab746c97dddc1028fded3d1113b5cfdd1ca82661347df3c5e8f0c'
API_URL = '/api/22443.xml'
#API_URL = 

# Opening the data logging file for reading
f=open('E:\Windows\WxLog.csv','r')
last_line=f.readlines()[-1]

last_line_arr = last_line.split(',')
print last_line_arr

readings = [last_line_arr[11],last_line_arr[13],last_line_arr[14],last_line_arr[16],last_line_arr[17],last_line_arr[19].rstrip()]
pac = eeml.Pachube(API_URL, API_KEY)
pac.update([eeml.Data(0, readings[0], unit=eeml.Celsius()), eeml.Data(1, readings[1], unit=eeml.RH()),eeml.Data(2, readings[2], unit=eeml.Celsius()),eeml.Data(3, readings[3], unit=eeml.RH()),eeml.Data(4, readings[4], unit=eeml.Celsius()),eeml.Data(5, readings[5], unit=eeml.RH())])
pac.put()
