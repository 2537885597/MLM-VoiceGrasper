import serial
import serial.tools.list_ports

WAKEUP_KEYWORDS = '小薇小薇'

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

def changehuan():
	head=0xA5
	userid=0x01
	msgtype=0x05
	#唤醒词
	msg=b'{"type": "wakeup_keywords","content": {"keyword": "xiao3 wei1 xiao3 wei1","threshold": "900"}}\n' #ni2 hao3 xiao3 yang2
	msglen_byte = len(msg).to_bytes(2, 'big') 

	msg_l = msglen_byte[1]
	msg_h= msglen_byte[0]
	msgid_l=0x01
	msgid_h=0x00
	checksum = ((~sum([head, userid, msgtype, msg_l, msg_h, msgid_l, msgid_h] + list(msg))) & 0xFF) +1
	head_byte = head.to_bytes(1, 'big')
	userid_byte = userid.to_bytes(1, 'big')
	msgtype_byte = msgtype.to_bytes(1, 'big')
	msg_l_byte = msg_l.to_bytes(1, 'big')
	msg_h_byte = msg_h.to_bytes(1, 'big')
	msgid_l_byte = msgid_l.to_bytes(1, 'big')
	msgid_h_byte = msgid_h.to_bytes(1, 'big')
	checksum_byte = checksum.to_bytes(1, 'big')
	complete_msg = head_byte + userid_byte + msgtype_byte + msg_l_byte + msg_h_byte + msgid_l_byte + msgid_h_byte + msg + checksum_byte
	return complete_msg



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
	print(head,userid,msgtype,data_len,msgid,data,check)
	break

ser.write(changehuan())

while 1:
	head = ser.read(1).hex()
	if head == "a5":
		userid = ser.read(1).hex()
		msgtype = ser.read(1).hex()

		len_l=ser.read(1).hex()
		len_h=ser.read(1).hex()	
		data_len = int(len_h+len_l, 16)

		msgid = ser.read(2).hex()
		data = ser.read(data_len)
		check = ser.read(1).hex()
		if msgtype=="ff":
			print(f"更改完成 请重新上电 唤醒词：{WAKEUP_KEYWORDS}")
			break

ser.close()
