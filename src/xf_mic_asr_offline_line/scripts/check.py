import serial
import serial.tools.list_ports

# 自动查找包含USB/ACM的串口（麦克风串口）
def find_mic_serial():
    ports = list(serial.tools.list_ports.comports())
    for port in ports:
        if "ACM" in port.device:
            return port.device
    return None

# 获取麦克风串口
mic_port = find_mic_serial()
if not mic_port:
    print("错误：未找到麦克风串口！")
    exit(1)

# 打开串口
ser = serial.Serial(mic_port, 115200, timeout=1)
print(f"自动识别并打开串口：{mic_port}")

#ser = serial.Serial('/dev/ttyACM1', 115200) #wheeltec_mic

while 1:
	head = ser.read(1).hex()
	if head != "a5":
		continue
	userid = ser.read(1).hex()
	msgtype = ser.read(1).hex()
	len_l=ser.read(1).hex()
	len_h=ser.read(1).hex()	
	data_len = int(len_h+len_l, 16)
	msgid = ser.read(2).hex()
	data = ser.read(data_len)
	check = ser.read(1).hex()
	print(msgtype,data)
ser.close()
