/*******************************************************
功能：麦克风音频数据采集节点
         发布PCM音频数据到 /pcm_audio_data 话题供语音识别使用
********************************************************/
#include <user_interface.h>
#include <string>
#include <locale>
#include <codecvt>
#include <ctime>
#include <joint.h>
#include <record.h>
#include <hidapi.h>

#include <ros/ros.h>
#include <mic_msg/mic_pcm_msg.h>

#include <std_msgs/Int8.h>
#include <std_srvs/Trigger.h>
#include <std_msgs/Int32.h>
#include <sys/stat.h>

/**************************************************************************
全局变量定义：发布者、话题名称、控制开关，供全文件调用
**************************************************************************/
// ros::Publisher voice_words_pub;
// ros::Publisher awake_flag_pub;
// ros::Publisher voice_flag_pub;
ros::Publisher pcm_data_pub;

// std::string voice_words = "voice_words";
// std::string voice_flag = "voice_flag";
// std::string awake_flag = "awake_flag";
std::string pcm_data_topic = "pcm_audio_data";
// std::string whole_result_topic = "whole_voice_result"; // 新增：完整识别结果的话题名称

// int offline_recognise_switch = 0; //离线识别默认开关

using namespace std;

/**************************************************************************
外部变量引用：来自其他文件的全局变量，用于数据共享
**************************************************************************/
// extern UserData asr_data;
extern int whether_finised ;
// extern char *whole_result;
// int set_led_id ;

extern int init_rec;
extern int init_success;
extern int write_first_data;

unsigned char* record_data;

/**************************************************************************
函数功能：字符串编码转换（UTF-8字符串→宽字符串）
入口参数：str - 待转换的UTF-8编码字符串（如识别到的中文命令词）
返回  值：转换后的宽字符串（wstring类型）
核心用途：处理中文识别结果的编码兼容问题，避免乱码
**************************************************************************/
std::wstring s2ws(const std::string &str)
{
	using convert_typeX = std::codecvt_utf8<wchar_t>;
	std::wstring_convert<convert_typeX, wchar_t> converterX;

	return converterX.from_bytes(str);
}

/**************************************************************************
函数功能：字符串编码转换（宽字符串→UTF-8字符串）
入口参数：wstr - 待转换的宽字符串
返回  值：转换后的UTF-8编码字符串（string类型）
核心用途：将处理后的宽字符串转回UTF-8，用于服务响应和话题发布
**************************************************************************/
std::string ws2s(const std::wstring &wstr)
{
	using convert_typeX = std::codecvt_utf8<wchar_t>;
	std::wstring_convert<convert_typeX, wchar_t> converterX;

	return converterX.to_bytes(wstr);
}

/*用于送入音频进行识别 (line)*/
/**************************************************************************
函数功能：音频数据处理函数（将录音数据送入语音识别引擎）
入口参数：record - 录音数据缓冲区（unsigned char*类型，存储PCM音频数据）
返回  值：无
核心逻辑：1. 缓存录音数据；2. 若初始化未完成但已触发，分配缓冲区并拷贝音频；
          3. 区分第一块/后续音频数据，调用识别引擎处理；4. 检测识别完成状态
**************************************************************************/
int business_data(unsigned char* record)
{
    record_data = record;
    if (!init_success && init_rec)
    {        
        int len = 30*PCM_MSG_LEN;  // 3*PCM_MSG_LEN=0.19s
        char *pcm_buffer=(char *)malloc(len);
        if (NULL == pcm_buffer)
		{
			printf(">>>>>buffer is null\n");
			exit (1);
		}
        memcpy(pcm_buffer, record_data, len);
        
        // // 注释掉命令词识别相关代码
        // if (write_first_data++ == 0)
        // {
		// 	// #if whether_print_log
		// 	// 		printf("***************write the first voice**********\n");
		// 	// #endif
        //     demo_xf_mic(pcm_buffer, len, 1);
        // }

        // else
        // {
		// 	// #if whether_print_log
		// 	// 		printf("***************write the middle voice**********\n");
		// 	// #endif
        //     demo_xf_mic(pcm_buffer, len, 2);
        // }
        if (whether_finised)
        {
            record_finish = 1;
            whether_finised = 0;
        }
		if (record_finish)
        {
			// 发布PCM音频数据话题
			mic_msg::mic_pcm_msg pcm_msg;
			pcm_msg.length = len;
			pcm_msg.pcm_buf.assign(pcm_buffer, pcm_buffer + len);
			pcm_data_pub.publish(pcm_msg);
			printf("发布 pcm 音频数据的话题消息\n");
        }
    }
	return 0;   
}


/*用于显示离线命令词识别结果*/
/**************************************************************************
函数功能：解析原始识别结果，提取有效关键字和置信度
入口参数：string - 原始识别结果（XML格式字符串，含<rawtext>和<confidence>标签）
返回  值：Effective_Result结构体（包含有效关键字effective_word和置信度effective_confidence）
核心逻辑：1. 查找XML标签位置；2. 提取置信度并转换为整数；3. 置信度达标则提取关键字；
          4. 填充结果结构体并返回（置信度不足则关键字为空）
**************************************************************************/
// Effective_Result show_result(char *string) //
// {
// 	Effective_Result current;
// 	if (strlen(string) > 250)
// 	{
// 		char asr_result[32];	//识别到的关键字的结果
// 		char asr_confidence[3]; //识别到的关键字的置信度
// 		char *p1 = strstr(string, "<rawtext>");
// 		char *p2 = strstr(string, "</rawtext>");
// 		int n1 = p1 - string + 1;
// 		int n2 = p2 - string + 1;

// 		char *p3 = strstr(string, "<confidence>");
// 		char *p4 = strstr(string, "</confidence>");
// 		int n3 = p3 - string + 1;
// 		int n4 = p4 - string + 1;
// 		for (int i = 0; i < 32; i++)
// 		{
// 			asr_result[i] = '\0';
// 		}

// 		strncpy(asr_confidence, string + n3 + strlen("<confidence>") - 1, n4 - n3 - strlen("<confidence>"));
// 		asr_confidence[n4 - n3 - strlen("<confidence>")] = '\0';
// 		int confidence_int = 0;
// 		confidence_int = atoi(asr_confidence);
// 		if (confidence_int >= confidence)
// 		{
// 			strncpy(asr_result, string + n1 + strlen("<rawtext>") - 1, n2 - n1 - strlen("<rawtext>"));
// 			asr_result[n2 - n1 - strlen("<rawtext>")] = '\0'; //加上字符串结束符。
// 		}
// 		else
// 		{
// 			strncpy(asr_result, "", 0);
// 		}

// 		current.effective_confidence = confidence_int;
// 		strcpy(current.effective_word, asr_result);
// 		return current;
// 	}
// 	else
// 	{
// 		current.effective_confidence = 0;
// 		strcpy(current.effective_word, " ");
// 		return current;
// 	}
// }

/*获取离线命令词识别结果*/
/**************************************************************************
函数功能：离线语音识别服务回调函数（核心业务逻辑）
入口参数：req - 服务请求（含识别启动开关、置信度阈值、识别超时时间）
          res - 服务响应（含识别结果状态、失败原因、有效关键字）
返回  值：bool - 服务调用是否成功（true-成功）
核心逻辑：1. 接收识别请求，开启离线识别；2. 创建识别引擎，获取音频数据；
          3. 解析识别结果，判断置信度是否达标；4. 填充服务响应，发布识别结果话题
**************************************************************************/
// bool Get_Offline_Recognise_Result(xf_mic_asr_offline_line::Get_Offline_Result_srv::Request &req,
// 								  xf_mic_asr_offline_line::Get_Offline_Result_srv::Response &res)
// {
// 	char *denoise_sound_path = join(source_path, DENOISE_SOUND_PATH);
// 	offline_recognise_switch = req.offline_recognise_start;
// 	if (offline_recognise_switch == 1) //如果是离线识别模式
// 	{
// 		whether_finised = 0;
// 		record_finish = 0;
// 		int ret = 0;
// 		ret = create_asr_engine(&asr_data);
// 		if (MSP_SUCCESS != ret)
// 		{
// #if whether_print_log
// 			printf("[01]创建语音识别引擎失败！\n");
// #endif
// 		}

// 		printf(">>>>>开始一次语音识别！\n");
// 		// 核心：获取实时录音（麦克风）
// 		// 不是读取录音文件，而是启动麦克风实时录音（denoise_sound_path 是降噪参考文件，不是识别的源音频文件）
// 		get_the_record_sound(denoise_sound_path);

// 		if (whole_result!="")
// 		{
// 			printf(">>>>>全部返回结果:　[ %s ]\n", whole_result);

// 			// // 新增：发布完整识别结果到话题
// 			// std_msgs::String whole_msg;
// 			// whole_msg.data = whole_result;
// 			// whole_result_pub.publish(whole_msg);
			
// 			Effective_Result effective_ans = show_result(whole_result);
// 			if (effective_ans.effective_confidence >= confidence) //如果大于置信度阈值则进行显示或者其他控制操作
// 			{
// 				printf(">>>>>是否识别成功:　 [ %s ]\n", "是");
// 				printf(">>>>>关键字的置信度: [ %d ]\n", effective_ans.effective_confidence);
// 				printf(">>>>>关键字识别结果: [ %s ]\n", effective_ans.effective_word);
// 				/*发布结果*/
// 				//control_jetbot(effective_ans.effective_word);
// 				res.result = "ok";
// 				res.fail_reason = "";
// 				std::wstring wtxt = s2ws(effective_ans.effective_word);
// 				std::string txt_uft8 = ws2s(wtxt);
// 				res.text = txt_uft8;
				
// 				std_msgs::String msg;
// 				msg.data = effective_ans.effective_word;
// 				voice_words_pub.publish(msg);
				
// 			}
// 			else
// 			{
// 				printf(">>>>>是否识别成功:　[ %s ]\n", "否");
// 				printf(">>>>>关键字的置信度: [ %d ]\n", effective_ans.effective_confidence);
// 				printf(">>>>>关键字置信度较低，文本不予显示\n");
// 				res.result = "fail";
// 				res.fail_reason = "low_confidence error or 11212_license_expired_error";
// 				res.text = " ";
// 			}
// 		}
// 		else
// 		{
// 			res.result = "fail";
// 			res.fail_reason = "no_valid_sound error";
// 			res.text = " ";
// 			printf(">>>>>未能检测到有效声音,请重试\n");
// 		}
// 		whole_result = "";
// 		/*[1-3]语音识别结束]*/
// 		delete_asr_engine();
// 		write_first_data = 0;
// 		sleep(1.0);
		
// 	}
// 	printf(" \n");
// 	printf(" \n");
// 	//ROS_INFO("close the offline recognise mode ...\n");
// 	return true;
// }

/**************************************************************************
函数功能：唤醒服务回调函数（核心业务逻辑）
入口参数：req - 服务请求（含唤醒启动开关）
          res - 服务响应（含唤醒状态）
返回  值：bool - 服务调用是否成功（true-成功）
核心逻辑：1. 接收唤醒请求，开启麦克风录音；2. 填充服务响应，发布唤醒状态话题
**************************************************************************/
bool Awake_Flag_Callback(std_srvs::TriggerRequest &req,
								  std_srvs::TriggerResponse &res)
{
	whether_finised = 0;
	record_finish = 0;
	printf(">>>>>开始一次麦克风录音！\n");
	char *denoise_sound_path = join(source_path, DENOISE_SOUND_PATH);
	printf(">>>>>denoise_sound_path = %s\n", denoise_sound_path);
		
	// 核心：获取实时录音（麦克风）
	// 不是读取录音文件，而是启动麦克风实时录音（denoise_sound_path 是降噪参考文件，不是识别的源音频文件）
	get_the_record_sound(denoise_sound_path);

	res.success = true;
	res.message = "record once";
	write_first_data = 0;
	return true;
}


/*程序入口*/
/**************************************************************************
函数功能：主函数（程序入口）
入口参数：argc - 命令行参数个数，argv - 命令行参数数组
返回  值：0（程序正常退出）
核心逻辑：1. 初始化ROS节点；2. 从参数服务器读取配置参数；3. 创建话题发布者；
          4. 启动异步自旋；5. 维持节点运行
**************************************************************************/
int main(int argc, char *argv[])
{
	// 初始化ROS节点，节点名称为"voice_control"
	ros::init(argc, argv, "voice_control");
	ros::NodeHandle ndHandle("~");
	/**************************************************************************
    参数读取：从ROS参数服务器获取配置参数，支持动态调整
    **************************************************************************/
	// ndHandle.param("/confidence", confidence, 0);				//离线命令词识别置信度阈值
	ndHandle.param("/seconds_per_order", time_per_order, 2); 	//单次录制音频的时长
	ndHandle.param("source_path", source_path, std::string("/home/rm/realman_ws/src/xf_mic_asr_offline_line"));
	ndHandle.param("/appid", appid, std::string("13869dba"));	//appid，需要更换为自己的

	// printf("-----confidence =%d\n",confidence);
	printf("-----time_per_order =%d\n",time_per_order);

	cout<<"-----source_path="<<source_path<<endl;
	cout<<"-----appid="<<appid<<endl;

	APPID = &appid[0];

	ros::NodeHandle n;

	/**************************************************************************
    通信对象创建：创建话题发布者
    **************************************************************************/
	// voice_words_pub = n.advertise<std_msgs::String>(voice_words, 1);

	// awake_flag_pub = n.advertise<std_msgs::Int8>(awake_flag, 1);

	// voice_flag_pub = n.advertise<std_msgs::Int8>(voice_flag, 1);

	pcm_data_pub = n.advertise<mic_msg::mic_pcm_msg>(pcm_data_topic, 1);

	/*srv　接收请求，返回离线命令词识别结果*/
	// ros::ServiceServer service_get_wav_list = ndHandle.advertiseService("get_offline_recognise_result_srv", Get_Offline_Recognise_Result);

	/*srv　接收唤醒请求，启动麦克风录音*/
	ros::ServiceServer awake_flag_srv = ndHandle.advertiseService("/awake_flag_service", Awake_Flag_Callback);

	/**************************************************************************
    语音识别资源初始化：拼接资源文件路径，初始化识别参数（登录+语法构建）
    **************************************************************************/
	// std::string begin = "fo|";
	// //std::string quit_begin = source_path;
	// char *jet_path = join((begin + source_path), ASR_RES_PATH);
	// char *grammer_path = join(source_path, GRM_BUILD_PATH);
	// char *bnf_path = join(source_path, GRM_FILE);
	// //IN_PCM = join(source_path, IN_PCM);
	// //[1-1] 通用登录及语法构建
	// // 初始化语音识别参数（登录服务+构建语法）
	// Recognise_Result inital = initial_asr_paramers(jet_path, grammer_path, bnf_path, LEX_NAME);

	// 重置初始化相关标志位
	init_rec = 0;
	init_success = 0;
	write_first_data = 0;
	
	// 启动异步自旋（3个线程，处理回调函数，不阻塞主循环）
	ros::AsyncSpinner spinner(3);
	spinner.start();

	/**************************************************************************
    主循环：维持节点运行
    **************************************************************************/
	printf("voice_control 节点已启动，等待回调...\n");
	while(ros::ok())
	{
		// 若初始化未成功，但已触发初始化（init_rec=1）
	    if (!init_success && init_rec)
	    {
	        // 获取当前时间
	        clock_t start, finish;
	        double total_time;
	        start = clock();
			// 循环等待初始化成功或识别完成
	        while (!init_success && whether_finised != 1)
	        {   
	            finish = clock();
	            total_time = (double)(finish - start) / CLOCKS_PER_SEC/2;
	            //printf(">>>>>total_time:　[ %f ]\n", total_time);
	            //printf(">>>>>whether_finised:　[ %d ]\n", whether_finised);
	            // 超出超时时间，标记录音完成并退出循环
				if (total_time > time_per_order)
	            {
	                printf(">>>>>超出离线命令词最长识别时间\n");
	                record_finish = 1; 
	                break;
	            }
	        } 
	    }	
	} 
	ros::spinOnce(); 
	// ros::waitForShutdown();
	return 0;
}
