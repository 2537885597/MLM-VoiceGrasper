 /* 功能描述: 基于ROS的Wheeltec麦克风唤醒节点
 *          1. 打开麦克风设备串口，接收串口数据
 *          2. 解析麦克风传输的JSON格式数据，提取唤醒状态和声音来源角度
 *          3. 发布唤醒标志、麦克风设备状态、唤醒词文本及声音来源角度话题
 *          4. 支持串口参数配置，适配不同硬件连接场景
 **核心功能模块:
 *          1. 串口通信模块 (open_port/set_opt): 打开并配置串口参数
 *          2. 数据解析模块 (deal_with): 解析串口接收的帧数据，提取JSON信息
 *          3. 校验模块 (check_sum): 计算数据校验和，确保数据完整性
 *          4. 数据转换模块 (data_trans): 字节数据转16位整型
 *          5. ROS通信模块: 发布各类状态和数据话题
 * 
 **ROS接口:
 *          - 话题发布:
 *              1. /awake_flag (std_msgs/Int8): 发布唤醒标志（1=唤醒，0=未唤醒）
 *              2. /voice_flag (std_msgs/Int8): 发布麦克风设备状态（1=设备正常）
 *              3. /voice_words (std_msgs/String): 发布唤醒提示文本（固定为"小微唤醒"）用于语音合成
 *              4. /mic/awake/angle (std_msgs/Int32): 发布声音来源角度（单位：度）
 * 
 **配置参数:
 *          - ~usart_port_name: 麦克风设备串口路径 (默认: /dev/wheeltec_mic)
 */
#include <com_mic.h>
#include <ros/ros.h>
#include <iostream>
#include <string.h>
#include <record.h>
#include "jsoncpp/json/json.h"
#include <std_msgs/Int32.h>
#include <std_msgs/Int8.h>
#include <std_srvs/Trigger.h>
#include <std_msgs/String.h>

#include <dirent.h>   // 新增：遍历目录所需头文件
// #include <fcntl.h>    // 新增：文件操作头文件
// #include <unistd.h>   // 新增：unistd头文件

using namespace std;

/**************************************************************************
全局变量定义：发布者、话题名称、串口配置、唤醒状态参数
**************************************************************************/
ros::Publisher awake_flag_pub;  // 唤醒标志位发布者（话题：awake_flag）
ros::ServiceClient awake_flag_client;  // 唤醒标志位服务客户端（服务：/awake_flag）
ros::Publisher voice_flag_pub;  // 语音功能开启标志位发布者（话题：voice_flag）
ros::Publisher voice_words_pub; // 唤醒命令词发布者（话题：voice_words）
ros::Publisher pub_awake_angle; // 唤醒角度发布者（话题：/mic/awake/angle）

std::string awake_flag = "awake_flag";
std::string awake_flag_service = "/awake_flag_service";
std::string voice_flag = "voice_flag";
std::string voice_words = "voice_words";
std::string awake_angle_topic = "/mic/awake/angle";
string usart_port_name;  // 串口名称（麦克风）

unsigned char Receive_Data[1024] = {0};
int angle_int = 0;
int if_awake = 0;

char awake_words[30] = "小微小微";

// /**************************************************************************
// 新增函数：自动识别麦克风串口（ttyACM*）
// 功能：遍历/dev目录，筛选出ttyACM串口，验证可打开后返回第一个有效串口
// 返回：有效串口路径（如"/dev/ttyACM1"），无则返回空字符串
// **************************************************************************/
// std::string auto_detect_mic_serial()
// {
//     DIR *dir;
//     struct dirent *ent;
//     // 待检查的串口前缀（优先ACM）
//     const char* prefixes[] = {"ttyACM"};
//     const int prefix_count = sizeof(prefixes)/sizeof(prefixes[0]);

//     // 打开/dev目录
//     if ((dir = opendir("/dev")) != NULL)
//     {
//         // 遍历前缀（先查ttyACM）
//         for(int p=0; p<prefix_count; p++)
//         {
//             rewinddir(dir); // 重置目录指针
//             const char* prefix = prefixes[p];
//             // 遍历/dev下的文件
//             while ((ent = readdir(dir)) != NULL)
//             {
//                 // 匹配前缀（如ttyACM0）
//                 if (strstr(ent->d_name, prefix) != NULL)
//                 {
//                     std::string serial_path = "/dev/";
//                     serial_path += ent->d_name;
                    
//                     // 验证串口是否可打开（只读模式，非阻塞）
//                     int fd = open(serial_path.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
//                     if (fd >= 0)
//                     {
//                         close(fd); // 验证后关闭
//                         ROS_INFO("✅ 自动识别到麦克风串口：%s", serial_path.c_str());
//                         closedir(dir);
//                         return serial_path;
//                     }
//                     else
//                     {
//                         ROS_WARN("⚠️  串口%s存在但无法打开（权限不足？）", serial_path.c_str());
//                     }
//                 }
//             }
//         }
//         closedir(dir);
//     }
//     else
//     {
//         ROS_ERROR("❌ 无法打开/dev目录！");
//     }

//     ROS_ERROR("❌ 未识别到任何有效串口（ttyACM*）");
//     return "";
// }

/**************************************************************************
函数功能：串口数据处理函数（核心帧解析逻辑）
入口参数：buffer - 串口读取的单个字节数据
返回  值：0（成功）
核心逻辑：1. 按自定义帧格式拼接字节数据；2. 校验帧头、用户ID合法性；3. 解析帧长度和消息ID；
          4. 帧接收完整后校验和；5. 解析JSON格式的唤醒数据，提取唤醒角度
**************************************************************************/
int deal_with(unsigned char buffer)
{
	static int count=0, frame_len=0, msg_id=0;
	Receive_Data[count] = buffer;
    // 新增：打印拼接中的字节（看串口数据具体是什么）
    // printf("拼接字节：count=%d, 字节值=0x%02x\n", count, buffer);
    if(Receive_Data[0] != FRAME_HEADER || (count == 1 && Receive_Data[1] != USER_ID))  //frame header and user id
    {
        // printf("帧头/用户ID不匹配：FRAME_HEADER=0x%02x, 实际帧头=0x%02x; USER_ID=0x%02x, 实际用户ID=0x%02x\n", 
        FRAME_HEADER, Receive_Data[0], USER_ID, Receive_Data[1]; // 新增：打印不匹配原因
        count = 0,frame_len = 0, msg_id = 0;
    }
    else 
        count++;
	if (count == 7){  //length and msg id
        msg_id = data_trans(Receive_Data[6], Receive_Data[5]);
        frame_len = data_trans(Receive_Data[4], Receive_Data[3]) + 7 + 1;
        // 新增：打印帧长度和消息ID
        // printf("解析帧长度：frame_len=%d, msg_id=%d\n", frame_len, msg_id);
	}
	if(count == frame_len){
		char str[1024] = {0};
        // 新增：打印完整帧数据（方便核对）
		// printf("完整帧数据（共%d字节）：", frame_len);
        // for(int i=0; i<frame_len; i++){
		// 	printf("0x%02x ", Receive_Data[i]);
		// }
		switch(Receive_Data[2]){
			case 0X01:
			/*
				if(check_sum(frame_len-1) == Receive_Data[frame_len-1]){
					for(int i=0; i<frame_len; i++){
						printf("%x ", Receive_Data[i]);
					}
					printf("\n");
				}
				else{
					printf("check failed !\n");
				}
				*/
                ROS_INFO_THROTTLE(20,  "Receive 0X01 frame(non-wake frame)\n"); // 新增：标注普通帧
				break;
			
			case 0X04:
                ROS_INFO_THROTTLE(20,  "Receive 0X04 wake frame\n"); // 新增：标注唤醒帧
				if(check_sum(frame_len-1) == Receive_Data[frame_len-1]){
					if_awake = 1;
					for(int i=0; i<frame_len-8; i++){
						str[i] = Receive_Data[i+7];
					}
					//printf("%s\n", str);
					//printf("check = %x \n", check_sum(frame_len-1));

					Json::Reader reader;
					Json::Value value;
					Json::Value value_iwv;

				    if(reader.parse(str,value))
				    {
				    	Json::Value content = value["content"];
				    	std::string iwv_msg = content["info"].asString();
				    	//cout << "iwv_msg is " << iwv_msg << endl;

				    	if (reader.parse(iwv_msg,value_iwv))
				    	{
				    		angle_int = value_iwv["ivw"]["angle"].asInt();
				    		//cout << "angle is " << angle_int << endl;
				    	}
				    }
				    else{
				    	 cout << "reader json fail!"<< endl;
				    }

				}
				else{
					printf("check failed !\n");
				}
				break;
				
			default:
               ROS_INFO_THROTTLE(20,  "Receive unknown frame type: 0x%02x(not 0X01/0X04)\n", Receive_Data[2]); // 新增：未知帧类型
				break;
		}
		
		count = 0,frame_len = 0, msg_id = 0;
		memset(Receive_Data, 0, 1024);
	}
	return 0;
}

/**************************************************************************
函数功能：校验和计算函数（异或校验？此处为累加取反加1）
入口参数：count_num - 需计算校验和的字节数（帧头到数据段的总长度）
返回  值：计算得到的校验位（unsigned char类型）
核心逻辑：累加指定长度的字节数据，结果取反后加1（补码形式）
**************************************************************************/
unsigned char check_sum(int count_num)
{
	unsigned char check_sum = 0;
	for(int i=0; i<count_num; i++){
		check_sum = check_sum + Receive_Data[i];
	}
	return ~check_sum+1;
}

/**************************************************************************
函数功能：字节转换函数（将两个8位字节转换为16位整数）
入口参数：data_high - 高8位字节，data_low - 低8位字节
返回  值：转换后的16位整数（short类型）
核心逻辑：通过位运算将高低字节拼接为16位数据
**************************************************************************/
short data_trans(unsigned char data_high, unsigned char data_low)
{
	short transition_16;
	transition_16 = 0;
	transition_16 |=  data_high<<8;   
	transition_16 |=  data_low;
	return transition_16;
}

/**************************************************************************
函数功能：打开串口设备
入口参数：uartname - 串口设备名称（如"/dev/wheeltec_mic"）
返回  值：串口文件描述符（fd≥0为成功，-1为失败）
核心逻辑：1. 以读写、非终端控制、非阻塞模式打开串口；2. 恢复串口为阻塞模式；
          3. 验证是否为终端设备；4. 返回文件描述符
**************************************************************************/
int open_port(const char* uartname)
{
    int fd = open(uartname, O_RDWR|O_NOCTTY|O_NONBLOCK);
    if (-1 == fd)
    {
        perror("Can't Open Serial Port");
        return(-1);
    }
     /*恢复串口为阻塞状态*/
     if(fcntl(fd, F_SETFL, 0)<0)
     {
            printf("fcntl failed!\n");
     }else{
        //printf("fcntl=%d\n",fcntl(fd, F_SETFL,0));
     }
     /*测试是否为终端设备*/
     if(isatty(STDIN_FILENO)==0)
     {
        printf("standard input is not a terminal device\n");
     }
     else
     {
        //printf("isatty success!\n");
     }
     //printf("fd-open=%d\n",fd);
     return fd;
}

/**************************************************************************
函数功能：配置串口参数
入口参数：fd - 串口文件描述符；nSpeed - 波特率；nBits - 数据位；
          nEvent - 校验位（'O'-奇校验，'E'-偶校验，'N'-无校验）；nStop - 停止位（1或2）
返回  值：0（成功），-1（失败）
核心逻辑：通过termios结构体配置串口的波特率、数据位、校验位、停止位等参数
**************************************************************************/
int set_opt(int fd,int nSpeed, int nBits, unsigned char nEvent, int nStop)
{
    struct termios newtio,oldtio;
    if  ( tcgetattr( fd,&oldtio)  !=  0) {
        perror("SetupSerial 1");
        return -1;
    }
    bzero( &newtio, sizeof( newtio ) );
    newtio.c_cflag  |=  CLOCAL | CREAD;
    newtio.c_cflag &= ~CSIZE;

    switch( nBits )
    {
    case 7:
        newtio.c_cflag |= CS7;
        break;
    case 8:
        newtio.c_cflag |= CS8;
        break;
    }

    switch( nEvent )
    {
    case 'O':
        newtio.c_cflag |= PARENB;
        newtio.c_cflag |= PARODD;
        newtio.c_iflag |= (INPCK | ISTRIP);
        break;
    case 'E':
        newtio.c_iflag |= (INPCK | ISTRIP);
        newtio.c_cflag |= PARENB;
        newtio.c_cflag &= ~PARODD;
        break;
    case 'N':
        newtio.c_cflag &= ~PARENB;
        break;
    }

    switch( nSpeed )
    {
    case 2400:
        cfsetispeed(&newtio, B2400);
        cfsetospeed(&newtio, B2400);
        break;
    case 4800:
        cfsetispeed(&newtio, B4800);
        cfsetospeed(&newtio, B4800);
        break;
    case 9600:
        cfsetispeed(&newtio, B9600);
        cfsetospeed(&newtio, B9600);
        break;
    case 115200:
        cfsetispeed(&newtio, B115200);
        cfsetospeed(&newtio, B115200);
        break;
    case 460800:
        cfsetispeed(&newtio, B460800);
        cfsetospeed(&newtio, B460800);
        break;
    case 921600:
        printf("B921600\n");
        cfsetispeed(&newtio, B921600);
                cfsetospeed(&newtio, B921600);
        break;
    default:
        cfsetispeed(&newtio, B9600);
        cfsetospeed(&newtio, B9600);
        break;
    }
    if( nStop == 1 )
        newtio.c_cflag &=  ~CSTOPB;
    else if ( nStop == 2 )
    newtio.c_cflag |=  CSTOPB;
    newtio.c_cc[VTIME]  = 0;
    newtio.c_cc[VMIN] = 0;
    tcflush(fd,TCIFLUSH);
    if((tcsetattr(fd,TCSANOW,&newtio))!=0)
    {
        perror("com set error");
        return -1;
    }
  //printf("set done!\n\r");
    return 0;
}
/**************************************************************************
函数功能：主函数
入口参数：无
返回  值：无
**************************************************************************/
int main(int argc, char** argv)
{

	ros::init(argc, argv, "wheeltec_mic");    //初始化ROS节点

	ros::NodeHandle node;    //创建句柄

	/***创建唤醒标志位话题发布者***/
	awake_flag_pub = node.advertise<std_msgs::Int8>(awake_flag,1);

    // 创建唤醒标志位服务客户端
    // awake_flag_client = node.serviceClient<std_srvs::Trigger>(awake_flag_service);

	/***创建麦克风设备串口打开话题发布者***/
	voice_flag_pub = node.advertise<std_msgs::Int8>(voice_flag, 1);

	/***创建命令词话题发布者***/
	voice_words_pub = node.advertise<std_msgs::String>(voice_words, 1);

	/*　topic 发布唤醒角度*/
	pub_awake_angle = node.advertise<std_msgs::Int32>(awake_angle_topic, 1);

    // /**************************************************************************
    // 新增逻辑：自动识别串口 + ROS参数优先级（参数>自动识别）
    // **************************************************************************/
    // std::string default_serial = auto_detect_mic_serial();

	ros::NodeHandle private_n("~");

	private_n.param<std::string>("usart_port_name",  usart_port_name,  std::string("/dev/wheeltec_mic")); // 原默认/dev/wheeltec_mic

    /**************************************************************************
    串口初始化：打开串口并配置参数
    **************************************************************************/
	int fd=1, read_num = 0;
    unsigned char buffer[1];
    memset(buffer, 0, 1);
    const char* uartname = usart_port_name.c_str();
    //printf("uartname is %s\n",uartname);
    // 打开串口
    if((fd=open_port(uartname))<0)
    {
        printf("open %s is failed\n",uartname);
        printf(">>>>>无法打开麦克风设备，尝试重新连接进行测试\n");
        return 0;
    }
    else{
        // 配置串口参数：波特率115200，数据位8，无校验，停止位1
        set_opt(fd, 115200, 8, 'N', 1);
        printf(">>>>>成功打开麦克风设备\n");
        printf(">>>>>唤醒词为:\"%s!\"\n",awake_words);
        //printf("set_opt fd=%d\n",fd);

        // 连续3次发布语音功能开启标志位（通知其他节点麦克风已就绪）
        for (int i = 0; i < 3; ++i)
        {
            std_msgs::Int8 voice_flag_msg;
            voice_flag_msg.data = 1;
            voice_flag_pub.publish(voice_flag_msg);
            //printf(">>>>>voice_flag_msg:%d\n", voice_flag_msg.data);
            sleep(1.0);
        }
    }
        
    /**************************************************************************
    主循环：持续读取串口数据，处理唤醒事件
    **************************************************************************/
	while(ros::ok())
	{
		memset(buffer, 0, 1);   // 清空缓冲区
		read_num = read(fd, buffer, 1); // 从串口读取1字节数据
        // 读取到数据时，调用deal_with函数解析
		if(read_num>0){
            // cout << "read_num" << endl;
			deal_with(buffer[0]);
        }
        // 检测到唤醒（if_awake=1），发布相关话题
        if(if_awake)
        {
        	printf(">>>>>唤醒角度为:%d\n", angle_int);
            // 发布唤醒角度
    		std_msgs::Int32 awake_angle;
			awake_angle.data = angle_int;
			pub_awake_angle.publish(awake_angle);
            // 发布唤醒标志位（1-已唤醒）
            std_msgs::Int8 awake_flag_msg;
			awake_flag_msg.data = 1;
			awake_flag_pub.publish(awake_flag_msg);

            // // 调用唤醒标志位服务（通知其他节点已唤醒）
            // while (!ros::service::waitForService(awake_flag_service, ros::Duration(1.0)))
            // {
            //     ROS_WARN("等待唤醒服务上线中...");
            // }
            // std_srvs::Trigger awake_flag_srv;
            // awake_flag_client.call(awake_flag_srv);

            // 发布唤醒命令词（"小微唤醒"）
			std_msgs::String msg;
			msg.data = "小微唤醒";
			voice_words_pub.publish(msg);

			sleep(1);
			if_awake = 0;
		} 
		ros::spinOnce(); 
		//ros::spin();     
	}
	return 0;

}