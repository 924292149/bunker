#!/usr/bin/env python3
#coding:utf-8
import os
import re
import time
import datetime
import json
import socket
from collections import Counter

'''
ssd测试过程中用到的类信息
'''

def list_to_dict(list_info, sep=':'):   # 输入列表， 以分隔符分隔， 输出字典
    '''将包含冒号的长字符串转换为字典格式'''
    list_temp = [] 
    
    for line in list_info:
        if line.count(sep) != 1:
            continue
        seprate_line = re.split(sep, line)
        seprate_line = [x.strip('/n').strip() for x in seprate_line]
        list_temp.append(seprate_line)
    
    dict_info = dict(list_temp)
    
    return dict_info


class SSD():
    '''一次模拟SSD的尝试'''
    def __init__(self, node):
        self.node = node
        self.diskname = re.split('/', self.node)[-1]
        self.info = {}
        # self.pcispeed = ''
        # self.boot = ''
        # self.names = {} # [sn, mn, cap, boot, namespace]
        # self.status = {}    # [status, pcispeed, temps, cap_status, dev_status_up, current_pwr, ddr_err_bit, gpio_err_bit, pcie_voltage]
        # self.vers = {}  # [fw, fwld, fmt, uefi_driver]
        # self.counters = {}  # [powerCycles, powerOnHours, unsafe_shutdowns, full_rebulid, raw_rebuild]
        # self.err = {} # [pcie_uncorr_err, pcie_fatal_err, nand_init_fail, nand_erase_err, nand_program_err, media_err,init_pcie_vot_low_cnt, rt_pcie_vot_low_cnt]
    def load(self): 
        '''更新ssd状态信息'''
        # 获取pci速度信息
        get_pci_speed_cmd = "find /sys/* -name {0}|grep devices|cut -d '/' -f 6|xargs lspci -vvv -s|grep 'LnkSta:'|cut -d ' ' -f 2,4".format(self.diskname)
        pci_speed_info = os.popen(get_pci_speed_cmd).readlines()[0].strip('\n')
        pci_speed_processed = ''.join(pci_speed_info.split(','))
        self.info['pcispeed'] = pci_speed_processed
        
        # 获取boot 信息
        get_boot_drive_cmd = "df -h | grep -E '/boot$'"
        boot_drive_info = os.popen(get_boot_drive_cmd).readlines()[0]
        if self.diskname in boot_drive_info:
            boot = 'Master'
        else:
            boot = 'Slave'
        self.info['boot'] = boot
        
        # 获取dera info信息并添加到字典
        get_dera_info_cmd = "./nvme dera info {0}".format(self.node)
        dera_info = os.popen(get_dera_info_cmd).readlines()
        self.info.update(list_to_dict(dera_info))

        # 获取status信息并添加到字典
        get_dera_state_cmd = "./nvme dera state {0}".format(self.node)
        dera_state = os.popen(get_dera_state_cmd).readlines()
        self.info.update(list_to_dict(dera_state))        
        return


def get_running_script():   # 获取当前正在运行的脚本及参数，pid. 返回列表[[command1, args, pid]]
    '''获取当前正在运行的脚本及参数，pid. 返回列表[[command1, args, pid]]'''
    commands = []
    # 使用ps命令查看当前进程信息是否包含脚本名
    get_python3_script_fullname_cmd =  "ps -elf | grep -E 'HotPlug_NVMe_suite\.py|ts_.*\.py.*|runvdb.py.*'|grep -v grep"
    running_script_full_name = os.popen(get_python3_script_fullname_cmd).readlines()
    # 对返回的进程信息逐条进行拆分，拆分为命令本身和参数
    for cmd in running_script_full_name:
        # 使用正则表达式对进行信息进行拆分，以空格为分隔符
        cmd_tmp = re.split(' ', cmd)
        cmd_tmp = [x for x in cmd_tmp if x] # 去掉空字符
        for splited_cmd in cmd_tmp:
            command = []
            # 定位脚本名，及所在位置
            if '.py' in splited_cmd:
                pid = cmd_tmp[3]
                running_script_cmd = splited_cmd
                # 将脚本名后面的字符串作为参数，重新整合格式[command, args]
                running_script_args = ' '.join(cmd_tmp[cmd_tmp.index(splited_cmd)+1:]) # 截取脚本名后面的项，整合为空格分隔的字符串
                running_script_args = running_script_args.strip('\n')
                command = [running_script_cmd, running_script_args, pid]
                commands.append(command)
    return commands


def get_machine_status():   # 获取当前测试机信息，[厂商, 型号, cpu, 内存, nvme node, 开机时间, 网络状态]
    '''获取当前测试机信息，[厂商, 型号, cpu, 内存, nvme node, 开机时间, 网络状态]'''
    # 定义相关命令
    get_manufacturer_command = 'dmidecode -s system-manufacturer && dmidecode -s system-product-name'
    get_cpu_type_command = 'dmidecode -s processor-version'
    get_mem_count_command = 'dmidecode -t memory | grep Size: | grep -v No'
    get_men_type_command = "dmidecode -t memory | grep 'Type: DDR'|uniq"
    get_uptime_command = "cat /proc/uptime | cut -d ' ' -f 1"
    get_nvme_node_command = "ls /dev/nvme* | grep nvme.$"
    
    # 获取服务器厂商，型号信息
    machine_info = os.popen(get_manufacturer_command).readlines()
    machine_info = [x.strip('\n').strip() for x in machine_info]
    manufacturer, machine_type = machine_info
    # 获取服务器CPU信息
    cpu_info = os.popen(get_cpu_type_command).readlines()
    cpu_info = [x.strip('\n').strip() for x in cpu_info]
    cpus = ' '.join(['{0} * {1}'.format(str(x), str(y)) for x, y in Counter(cpu_info).items()])
    # 获取服务器内存信息
    mem_count = os.popen(get_mem_count_command).readlines()
    mem_count  = [x.strip('\n').strip() for x in mem_count]
    mem_type = os.popen(get_men_type_command).readlines()
    mem_type = [x.strip('\n').strip() for x in mem_type][0]
    mem_dict = Counter(mem_count)
    mems = ' '.join(['{0} * {1} {2}'.format(str(x), str(y), mem_type) for x, y in mem_dict.items()])
    # 获取dera nvme ssd字符设备信息
    node_info = os.popen(get_nvme_node_command).readlines()
    node_info = [x.strip('\n').strip() for x in node_info]
    for node in node_info:
        identify_info = os.popen("./nvme id-ctrl {0} | grep ^vid | cut -d ':' -f 2".format(node)).readlines()
        identify_info = [x.strip('\n').strip() for x in identify_info][0]
        if identify_info != '0x1d78':   # 排除非dera ssd
            node_info.remove(node)
    # 获取服务器开机时长信息
    uptime_seconds = os.popen(get_uptime_command).readlines()[0]
    uptime_seconds = float(uptime_seconds)
    m, s = divmod(uptime_seconds, 60)
    h, m = divmod(m, 60)
    uptime = "%02d:%02d:%02d" % (h, m, s)
    # 获取服务器当前网络状态信息
    local = '10.0.4.1' # 本地网关
    t_disk = '10.0.1.206' # T盘所在服务器的IP地址
    internet = 'www.baidu.com'  # 外网
    net_bucket = [local, t_disk, internet]
    net_status = ['1', '1', '1']
    for ip in net_bucket:
        ping_command = 'ping {0} -c 1 -w 1'.format(ip)
        respond = os.popen(ping_command).readlines()
        for line in respond:
            if 'ttl' in line:
                index = net_bucket.index(ip)
                net_status[index] = '0'
            else:
                pass
    net_status = ''.join(net_status)

    return [manufacturer, machine_type, cpus, mems, node_info, uptime, net_status]


def main():
    
    # def env_chcek():
        # install dmidecode newer than v2.8
        

    def timeStamp():
        now_time = datetime.datetime.now()
        readable_time = now_time.strftime('%Y-%m-%d_%H_%M_%S')
        return readable_time
    
    def list_compare(current_list, last_list):
        # 以第一个列表为基准，返回相对于第二个列表来说，增加的元素列表，和减少的元素列表
        item_add = []
        item_remove = []
        for current_item in current_list:
            if current_item not in last_list:
                item_add.append(current_item)
            else:
                last_list.remove(current_item)
        if last_list:
            item_remove = last_list
        return item_add, item_remove

    def genarate_current_trace():  
        '''获取当前运行的脚本，机器状态，及ssd实例'''
        traces = []
        scripts = get_running_script()
        machine = get_machine_status()
        ssd = []
        for ssd_node in machine[4]:
            var_name = 'nvme%s'%str(machine[4].index(ssd_node))
            locals()[var_name] = SSD(ssd_node)
            ssd.append(locals()[var_name])
        # 以nvme ssd作为标的物，生成trace
        for nvme in ssd:
            nvme.load()
            node = nvme.node
            running_script = ''
            
            if scripts:
                for script in scripts:
                    if 'ts_pwr.py' in script[0]:    # 由于ts_pwr和ts_top带有掉电测试，所以是全局式的脚本，所有ssd均受影响，所以只要有一个SSD在运行该测试，则认为所有ssd均受此影响
                        running_script = script
                    elif 'ts_top.py' in script[0]:
                        running_script = script
                    elif node in script[1]:
                        running_script = script
                    else:
                        pass
            add_machine_and_script = dict([['machine', machine], ['script', running_script]])
            trace = nvme.info
            trace.update(add_machine_and_script)
            traces.append(trace)

        return traces
    
    def read_old_trace(file_name='last_trace.json'):
        if os.path.exists(file_name):
            with open(file_name) as last_trace_obj:
                old_traces = json.load(last_trace_obj)
        else:
            old_traces = []
        return old_traces

    def send_info(data, server_ip='10.0.4.68'):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((server_ip, 6001))
        s.send((data).encode('utf-8'))  # 发送客户端有效数据
        # print(s.recv(1024).decode('utf-8')) # 接受服务器端的返回信息
        s.send(('').encode('utf-8'))    # 发送终止信息（空字符）
        s.close()   # 关闭连接
        return

    # -------- 以下为主要逻辑区域 --------
    current_traces = genarate_current_trace()
    old_traces = read_old_trace()


    def core_logic(current_traces, old_traces):
        
        def process_card_add(add_card):
            '''
            生成特定识别信息，转交发送函数，发送给服务器
            '''
            # ['N', timestamp, current_trace]
            now_time = timeStamp()
            new_traces = []
            for sn in add_card:
                for trace in current_traces:
                    if trace['SN'] == sn:
                        new_trace = ['N', now_time, trace]
                        new_traces.append(new_trace)
            json_info = json.dumps(new_traces)
            send_info(json_info)  # 发送给服务器

            return

        def process_card_remove(remove_card):
            '''
            构建一条新的消息，格式如下，
            报告给中央服务器，该卡已经在机器上被移除了
            '''
            # ['R', timestamp, sn, err] 
            now_time = timeStamp()
            new_traces = []
            for sn in remove_card:
                for old_trace in old_traces:            
                    if old_trace['SN'] == sn:
                        if old_trace['script'] == '':
                            err = 0
                        else:
                            err = 1
                    new_trace = ['R', now_time, sn, err]
                    new_traces.append(new_trace)
            json_info = json.dumps(new_traces)
            send_to_server = send_info(json_info)  # 发送给服务器
            return

        def process_normal_mode(normal_cards_sn):
            '''
            即不存在新插入卡，也不存在移除卡的情况下，执行该函数，
            该函数比较相同sn的ssd在两次不同时间的扫描下，各项信息是否一致，并通知给主控服务器
            '''
            now_time = timeStamp()
            new_traces = []

            for sn in normal_cards_sn:
                single_card_info = []
                
                current_trace = [trace for trace in current_traces if trace['SN'] == sn][0]
                old_trace = [trace for trace in old_traces if trace['SN'] == sn][0]

                for key in current_trace:
                    if key in old_trace:
                        if current_trace[key] != old_trace[key]:
                           single_info = [key, old_trace[key], current_trace[key]]
                           single_card_info.append(single_info)
                        else:
                            continue
                if single_card_info:
                    new_traces.append(single_card_info)
            if new_traces:
                json_info = json.dumps(new_traces)
                send_info(json_info) 
                    
            #     for key in current_trace:
            #         if key in old_trace:
            #             if current_trace[key] != old_trace[key]:
            #                info = [key, old_trace[key], current_trace[key]]#'{0}: {1} ==> {2}\n'.format(key, old_trace[key], current_trace[key])
            #             else:
            #                 info = []
            #         else:
            #             info = [key, current_trace[key]]#'{0}: ? ==> {1}\n'.format(key, current_trace[key])
            #         if info:
            #             change_info.append(info)           
            #     if change_info:        
            #         new_trace = ['C', now_time, sn, change_info]
            #         new_traces.append(new_trace)
            # if new_traces:
            #     json_info = json.dumps(new_traces)
            #     send_to_server = send_info(json_info)  # 发送给服务器
            # else:
            #     pass    # 后期可添加心跳函数

            return

     
        current_cards_sn = [trace['SN'] for trace in current_traces  if current_traces]  # 获取当前trace中ssd的names部分
        last_cards_sn = [trace['SN'] for trace in old_traces if old_traces] # 获取上次扫描中ssd的names部分
        add_card, remove_card = list_compare(current_cards_sn, last_cards_sn) # 判断是否有丢卡，或新识别卡的情况发生
        normal_cards_sn = [x for x in current_cards_sn if x not in add_card] # 既不是新添加的卡，也不包含弹出的卡

#-------- 处理新卡插入动作 --------
        if add_card:    # 处理新识别卡，这种情况
            process_card_add(add_card)
#-------- 处理卡弹出/丢卡动作 ------
        if remove_card:
<<<<<<< HEAD
            process_card_remove(remove_card)
#-------- 处理卡信息变动动作 ------
        process_normal_mode(normal_cards_sn)
        return
=======
            def process_card_remove(remove_card):
                '''
                1.构建新trace
                2.检查上次状态是否为idle
                3.如果上次为idle，则判断本次卡移除动作为正常弹出，报卡弹出给server端, 归档trace
                4.如果上次为running，则判断本次卡移出动作为丢卡，走丢卡流程， 归档trace
                '''
                # ['R', timestamp, sn, err] 
                now_time = timeStamp()
                new_traces = []
                for sn in remove_card:
                    for old_trace in old_traces:            
                        if old_trace['SN'] == sn:
                            if old_trace['script'] == '':
                                err = 0
                            else:
                                err = 1
                        new_trace = ['R', now_time, sn, err]
                        new_traces.append(new_trace)
                send_to_server = send_info(new_traces)  # 发送给服务器
                return
            process_card_remove(remove_card)
            
#-------- 处理卡信息变动动作 ------
        def process_normal_mode(normal_card):
            '''
            '''
            # current_time = timeStamp()
            # old_trace = []
            # current_trace = []
            # update_info = [current_time]

            # if not normal_card:
            #     return
            # for card_name in normal_card:
            #     for trace in current_traces:
            #         if card_name == trace[0]:
            #             current_trace = trace
            #     for trace in old_traces:
            #         if card_name == trace[0]:
            #             old_trace = trace
            #     # 重构需要比对的变量


#-------- 检测卡关键信息变动 --------#
                # if current_trace[1] != old_trace[1]:
                #     def process_firmware_change(current_vers, old_vers): # ['v', 'firmware-change:....', 'format-change:...']
                #         detect = ['v']
                        
                #         if not current_vers or not old_vers:
                #             return 1
                #         c_fw, c_fwld, c_fmt, c_uefi_driver = current_vers
                #         o_fw, o_fwld, o_fmt, o_uefi_driver = old_vers
                        
                #         if c_fw != o_fw:
                #             info = 'firmware-change: {0} ==> {1}'.format(o_fw, c_fw)
                #             detect.append(info)
                #         if c_fwld != o_fwld:
                #             info = 'fwld-change: {0} ==> {1}'.format(o_fwld, c_fwld)
                #             detect.append(info)
                #         if c_fmt != o_fmt:
                #             info = 'format-change: {0} ==> {1}'.format(o_fmt, c_fmt)
                #             detect.append(info)
                #         if c_uefi_driver != o_uefi_driver:
                #             info = 'uefi_driver-change: {0} ==> {1}'.format(o_uefi_driver, c_uefi_driver)
                #             detect.append(info)

                #         return detect
                #     current_vers = current_trace[1]
                #     old_vers = old_trace[1]
                #     version_change = process_firmware_change(current_vers, old_vers)               
>>>>>>> 54190ebcb0c0ea6261e97956afed1d3934263a59

    # def env_chcek():
    #     install dmidecode newer than v2.8
    
    while True:
        
        current_trace = genarate_current_trace()
        old_traces = read_old_trace()
        core_logic(current_trace, old_traces)
        with open('last_trace.json', 'w') as last_trace_obj:
            json.dump(current_trace, last_trace_obj)
            last_trace_obj.close()
        time.sleep(10)
main()
        # 接下来是比对逻辑, 检查SSD信息变动


        
        
        # 将数据存储到本地文件
        # with open('last_scan.pickle', 'wb') as last_scan:
        #     pickle.dump(traces, last_scan)
        # time.sleep(2)


