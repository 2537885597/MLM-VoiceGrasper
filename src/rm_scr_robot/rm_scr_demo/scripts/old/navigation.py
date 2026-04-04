import socket
import json

def get_current_map():
    """
    获取当前地图列表并输出地图名和楼层
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('192.168.10.10', 31001)
    
    try:
        sock.connect(server_address)
        
        # 发送获取当前地图请求
        message = '/api/map/get_current_map'
        sock.sendall(message.encode('utf-8'))

        # 接收响应
        data = sock.recv(4096)
        json_data = json.loads(data.decode('utf-8'))
        
        if json_data["status"] == "OK":
            results = json_data["results"]
            map_name = results.get("map_name", "未知地图")
            floor = results.get("floor", "未知楼层")
            
            print(f"当前地图名称: {map_name}")
            print(f"当前楼层: {floor}")
 
        else:
            print(f"获取当前地图失败: {json_data['error_message']}")

    except Exception as e:
        print(f"发生错误: {str(e)}")
    finally:
        sock.close()

def go_to_marker(marker: str):
    """
    导航到指定路标marker
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('192.168.10.10', 31001)
    sock.connect(server_address)

    try:
        message = f'/api/move?marker={marker}'
        sock.sendall(message.encode('utf-8'))

        act = True
        while act:
            data = sock.recv(4096)
            if not data:
                break

            try:
                for line in data.decode('utf-8').splitlines():
                    if line.strip():
                        json_data = json.loads(line)
                        print(json_data)
                        if "code" in json_data and json_data['code'] in ['01002', '01003']:
                            act = False
            except:
                print("error")
                print(data.decode('utf-8'))
                sock.close()

    finally:
        print("关闭连接")
        sock.close()

def patrol_markers(markers, tolerance=0.2, count=1):
    """
    对markers列表内的路标进行巡游
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_address = ('192.168.10.10', 31001)
    sock.connect(server_address)

    try:
        markers = ','.join(markers)
        message = f'/api/move?markers={markers}&distance_tolerance={tolerance}&count={count}'
        sock.sendall(message.encode('utf-8'))

        act = True
        while act:
            data = sock.recv(4096)
            if not data:
                break

            try:
                for line in data.decode('utf-8').splitlines():
                    if line.strip():
                        json_data = json.loads(line)
                        print(json_data)
                        if "code" in json_data and json_data['code'] in ['01102', '01103']:
                            act = False
            except:
                print("error")
                print(data.decode('utf-8'))
                sock.close()

    finally:
        print("关闭导航连接")
        sock.close()

if __name__ == "__main__":
    # 获取地图列表
    get_current_map()
    
    # 示例使用
    go_to_marker("m1")
    # markers = [f"m{i}" for i in range(1, 5)]
    # markers = ['charger', 'door', 'm1', 'm2', 'charger']
    # patrol_markers(markers)