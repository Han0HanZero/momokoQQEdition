import asyncio

import websockets
import json
from haversine import haversine
import math
import requests
from loguru import logger


from websockets import ConnectionClosedError

logger.add("./logs/bot_alpha.log", rotation="1 day", retention="7 days", enqueue=True)


class Chat:
    """
    GroupChat或C2CChat拥有openid:str、type:str、name:str、members:list四个属性。members中每个元素都是一个User对象。特别地，C2CChat中members仅有一个元素。
    """
    def __init__(self, chat_config:dict):
        self.openid = chat_config['openid']
        self.type = None
        self.name = ''
        self.members = []


class C2CChat(Chat):
    """
    GroupChat或C2CChat拥有openid:str、type:str、name:str、members:list四个属性。members中每个元素都是一个User对象。特别地，C2CChat中members仅有一个元素。
    """
    def __init__(self, c2c_user_config:dict):
        super().__init__(c2c_user_config)
        self.type = 'c2c'
        self.name = c2c_user_config['name']
        self.members.append(User(c2c_user_config))

class GroupChat(Chat):
    """
    GroupChat或C2CChat拥有openid:str、type:str、name:str、members:list四个属性。members中每个元素都是一个User对象。
    """
    def __init__(self, group_config:dict):
        super().__init__(group_config)
        self.type = 'group'
        self.name = group_config['name']
        for member_config in group_config['members']:
            user = User(member_config)
            self.members.append(user)


class Eew:
    def __init__(self, reception_dic:dict):
        self.report_num = reception_dic['ReportNum']
        self.origin_time = reception_dic['OriginTime']
        self.hypo_center = reception_dic['HypoCenter']
        self.latitude = reception_dic['Latitude']
        self.longitude = reception_dic['Longitude']
        self.magnitude = reception_dic['Magnitude']
        self.depth = reception_dic['Depth']
        self.max_intensity = reception_dic['MaxIntensity']


class User:
    def __init__(self, user_config:dict):
        self.name = user_config['name']
        self.openid = user_config['openid']
        self.latitude = user_config['location'][0]
        self.longitude = user_config['location'][1]
        self.distance = 0
        self.local_intensity = 0
        self.affected = False
        self.level = '🔵'

    def calc_local_intensity(self, eew:Eew) -> None:
        user_location = (self.latitude, self.longitude)
        hypo_center_location = (eew.latitude, eew.longitude)
        self.distance = haversine(user_location, hypo_center_location)
        if self.distance <= 50:
            self.local_intensity = eew.max_intensity
        else:
            magnitude = eew.magnitude
            self.local_intensity = 2.726 + 1.335 * magnitude - 3.318 * math.log10(self.distance)  # HCIEM v1
            if self.local_intensity >= 1.5:
                self.affected = True
                if self.local_intensity < 2.5:
                    self.level = '🔵'
                elif self.local_intensity < 4.5:
                    self.level = '🟡'
                elif self.local_intensity < 6.5:
                    self.level = '🟠'
                else:
                    self.level = '🔴'

class Payload:
    def __init__(self, id:str|None=None, op:int|None=None, d:dict|None=None, s:int|None=None, t:str|None=None):
        self.id = id
        self.op = op
        self.d = d
        self.s = s
        self.t = t
    def load(self) -> dict:
        return {
            'id': self.id,
            'op': self.op,
            'd': self.d,
            's': self.s,
            't': self.t
        }


def get_config() -> dict:
    try:
        with open('config.json','r') as f:
            config = json.load(f)
            logger.success('config获取成功')
            return config
    except FileNotFoundError:
        logger.critical('错误：config.json不存在！')
        exit(-1)
    except Exception as e:
        logger.error(f'错误：{repr(e)}')
    if not config:
        logger.critical('config获取失败')
        exit(-1)
    return config


def get_chat_config() -> dict:
    try:
        with open('chat_config.json','r') as f:
            chat_config = json.load(f)
            logger.success('chat_config获取成功')
            logger.info(chat_config)
            return chat_config
    except FileNotFoundError:
        logger.critical('错误：chat_config.json不存在！')
        exit(-1)
    except Exception as e:
        logger.error(f'错误：{repr(e)}')
    if not chat_config:
        logger.critical('chat_config获取失败')
        exit(-1)
    return chat_config


def get_access_token(config:dict) -> None|str:
    i = 1
    while i <= 5:  # 获取access_token
        try:
            access_token = requests.post('https://bots.qq.com/app/getAppAccessToken', json={
                'appId': str(config['app_id']),
                'clientSecret': config['secret']
            }).json()['access_token']
        except Exception as e:
            logger.error(f'警告！获取access token失败：{repr(e)}。这是第{i}次尝试。')
            if i >= 5:
                logger.error('获取access token失败')
                return None
            else:
                i += 1
                continue
        else:
            return access_token


def send(response:str, mentioned_users:list|str, config:dict, msg_type:str, target:C2CChat|GroupChat) -> bool:
    logger.info(f'准备发送：{response}')
    access_token = get_access_token(config)
    if type(target) == C2CChat:
        target_type = 'users'
    elif type(target) == GroupChat:
        target_type = 'groups'
    else:
        logger.error('传入send函数的target类型不明')
        return False
    i = 1
    while i <= 5:  # 发送消息
        try:
            result = requests.post(f'https://api.sgroup.qq.com/v2/{target_type}/{config["target_open_id"]}/messages',
                                   json={'content': response,
                                         'msg_type': 0},
                                   headers={
                                       'Authorization': f'QQBot {access_token}'
                                   })
            result.raise_for_status()
        except Exception as e:
            logger.error(f'警告！发送消息失败：{repr(e)}。这是第{i}次尝试。')
            if i >= 5:
                logger.error('发送失败')
                return False
            else:
                i += 1
        else:
            logger.success(f'发送消息成功！')
            return True


def instantiate_chats(chat_config:dict) -> list[GroupChat|C2CChat]:
    chats = []
    for group_config in chat_config['groups']:
        group = GroupChat(group_config)
        chats.append(group)
    for user_config in chat_config['users']:
        c2c_user = C2CChat(user_config)
        chats.append(c2c_user)
    return chats


def instantiate_debug_group_chat(chat_config:dict) -> GroupChat:
    return GroupChat(chat_config['debug_group'])


'''
def instantiate_users(user_config:dict) -> list:
    users = []
    try:
        for user_config in config['users']:
            users.append(User(user_config))
        return users
    except Exception as e:
        logger.critical('错误：实例化用户失败。')
        send('【instantiate_users】致命错误：实例化用户失败，检查config。',[],config,'debug')
        exit(-1)
'''


async def get_eew(uri:str, config:dict, chat_config:dict) -> None:
    debug_group_chat = instantiate_debug_group_chat(chat_config)
    i = 1
    #users = instantiate_users(config)
    while True:
        if i > 100:
            logger.critical('重试次数太多，进程已终止，请手动重启。')
            send('【get_eew】重试次数太多，进程已终止，请手动重启。',[],config,'debug',debug_group_chat)
            exit(-1)
        try:
            async with websockets.connect(uri) as websocket:
                logger.success('成功建立连接，等待......')
                send('【get_eew】成功连接服务器！',[],config,'debug',debug_group_chat)
                i = 1
                async for reception in websocket:  # 处理收到的包
                    logger.info('接收！'+str(reception))
                    is_send = False
                    affected_users = []
                    reception_dic = json.loads(reception)
                    if reception_dic['type'] == 'heartbeat':
                        logger.info('是心跳包')
                        continue
                    elif reception_dic['type'] == 'cenc_eew':
                        logger.info('是EEW')
                        eew = Eew(reception_dic)
                        chats = instantiate_chats(chat_config)
                        for chat in chats:  # 逐对话计算烈度
                            for user in chat.members:
                                user.calc_local_intensity(eew)
                                if user.local_intensity < config['threshold_intensity']:  # 判断是否应该发出
                                    is_send = False
                                    continue
                                else:
                                    is_send = True
                                    affected_users.append(user)
                            if is_send:  # 决定是否发出
                                response = f'⚠️即时地震信息⚠️\n{eew.origin_time}，{eew.hypo_center}发生了{str(eew.magnitude)}级地震，震源深度{str(eew.depth)}km，预估最大烈度{eew.max_intensity}。\n注意，以下群友可能受到影响：\n'
                                sorted_affected_users = sorted(affected_users, key=lambda u: u.local_intensity, reverse=True)
                                for user in sorted_affected_users:
                                    response += f'{user.level} {user.name} - 预估烈度{str(round(user.local_intensity))}\n'
                                response += "请立即避险！\n伏地·遮挡·手抓牢"
                                send(response, affected_users, config,'text',chat)  # 最终发送
                            else:
                                pass
                    elif reception_dic['type'] == 'cenc_eqlist':
                        logger.info('是地震情报')
                        continue
                    else:
                        logger.warning('未预期的类型')
                        send(f'【get_eew】类型未预期：{reception_dic["type"]}',[],config,'debug',debug_group_chat)
        except ConnectionClosedError:
            logger.error(f'连接断开，正在重新连接。这是第{i}次尝试。')
            if i == 1 or i % 10 == 0:
                send(f'【get_eew】连接断开，正在重新连接。这是第{i}次尝试。',[],config,'debug',debug_group_chat)
            i += 1
            await asyncio.sleep(3)
        except Exception as e:
            logger.error(f'出现未知错误：{repr(e)}。这是第{i}次尝试。')
            if i == 1 or i % 10 == 0:
                send(f'【get_eew】出现未知错误：{repr(e)}。这是第{i}次尝试。',[],config,'debug',debug_group_chat)
            i += 1


async def heartbeat(websocket, heartbeat_interval:int, state:dict):
    while True:
        try:
            await asyncio.sleep(heartbeat_interval)
            await websocket.send(json.dumps({'op': 1, "d": state['latest_s']}))
            logger.success('成功向QQ发送心跳包')
        except Exception as e:
            logger.error(f'发送心跳包失败：{e}')



async def listen(config:dict, state:dict, chat_config:dict) -> None:
    access_token = get_access_token(config)
    debug_group_chat = instantiate_debug_group_chat(chat_config)
    i = 1
    while True:
        try:
            uri = requests.get('https://api.sgroup.qq.com/gateway', headers={'Authorization': f'QQBot {access_token}'}).json()['url']
        except Exception as e:
            if i > 50:
                logger.critical('获取网关地址失败，请手动重启程序')
                send('【listen】获取网关地址失败，请手动重启',[],config,'debug',debug_group_chat)
                exit(-1)
            logger.error(f'获取网关地址失败:{e}。这是第{i}次尝试。')
            if i == 1 or i % 10 == 0:
                send(f'【listen】获取网关地址失败。这是第{i}次尝试。',[],config,'debug',debug_group_chat)
            i += 1
        else:
            logger.success(f'获取网关地址成功：{uri}')
            break
    i = 1
    connected = False
    while True:
        if i > 100:  # 监听启动失败
            logger.critical('监听启动失败，请手动重启')
            send('【listen】监听启动失败，请手动重启',[],config,'debug',debug_group_chat)
            exit(-1)
        try:
            access_token = get_access_token(config)
            async with websockets.connect(uri) as websocket:  # 尝试连接事件服务器
                logger.success('成功连接事件服务器！')
                send('【listen】成功连接事件服务器！',[],config,'debug',debug_group_chat)
                if not connected:  # 首次连接的话，尝试接受一个Hello包，发送一个Identify，并启动心跳协程
                    hello = json.loads(await websocket.recv())  # 接收Hello
                    logger.info(hello)
                    if hello['op'] == 10:  # 处理第一个包
                        logger.success(f'收到Hello包，要求的interval为{hello["d"]["heartbeat_interval"]}')
                        heartbeat_interval = hello['d']['heartbeat_interval'] / 1000 * 0.99
                        connected = True
                    else:
                        logger.critical(f'收到的Hello包不正常，其op为{hello["op"]}')
                        send(f'【listen】Hello包异常（{hello["op"]}），请手动重启。', [], config, 'debug',debug_group_chat)
                        exit(-1)
                    identify = json.dumps({
                        'op': 2,
                        'd':{
                            'token': f'QQBot {access_token}',
                            'intents': 1 << 25,
                            'shard': [0,1],
                            'properties': {}
                        }
                    })
                    logger.info(identify)
                    await websocket.send(identify)  # 发送Identify鉴权
                    ready = json.loads(await websocket.recv())  # 尝试接受Ready包
                    logger.info(ready)
                    if ready['op'] == 0 and ready['t'] == 'READY':  # 验证Ready包
                        logger.success('鉴权成功，监听开始')
                        i = 1
                        state['latest_s'] = ready['s']
                        session_id = ready['d']['session_id']
                        connected = True
                        asyncio.create_task(heartbeat(websocket, heartbeat_interval, state))
                    else:
                        logger.critical('鉴权失败，监听启动不正确')
                        exit(-1)
                else:  # 非首次连接（断开），尝试发送Resume包
                    await websocket.send(json.dumps({
                        'op': 6,
                        'd': {
                            'token': f'QQBot {access_token}',
                            'session_id': session_id,
                            'seq': state['latest_s']
                        }
                    }))  # 发送Resume
                # 以上为连接部分
                async for event in websocket:  # ===== 事件处理 =====
                    logger.info(event)
                    event = json.loads(event)
                    op = event['op']
                    if op == 0:  # 消息推送
                        pass
                    elif op == 1:  # 心跳
                        logger.warning('服务端似乎发送了一个心跳包？')
                        pass
                    elif op == 7:  # 需要重连
                        logger.error('服务端要求重新连接')
                        break
                    elif op == 9:  # session无效
                        logger.error('服务端称session无效')
                        connected = False
                        break
                    elif op == 10:  # Hello
                        logger.warning('服务端似乎发送了一个Hello包？？？')
                        pass
                    elif op == 11:  # 心跳ack
                        logger.info('收到心跳ack')
                        pass
                    else:
                        logger.error('收到了OpCode无法识别的包，请检查。')
                        pass
        except ConnectionClosedError:
            logger.error('与事件服务器连接中断')
            send('【listen】与事件服务器连接中断',[],config,'debug',debug_group_chat)


async def main():
    config = get_config()
    chat_config = get_chat_config()
    debug_group_chat = instantiate_debug_group_chat(chat_config)
    #is_send_debug = config['is_send_debug']
    state = {'latest_s': None}
    uri = config['eew_source']
    i = 1
    while True:
        try:
            #asyncio.create_task(listen(config, state))
            #asyncio.create_task(get_eew(uri,config))
            await asyncio.gather(listen(config, state, chat_config), get_eew(uri, config, chat_config))
        except (asyncio.exceptions.CancelledError, KeyboardInterrupt):
            logger.info('程序被手动终止，正在退出。')
            exit(0)
        except Exception as e:
            logger.error(f'错误！main()出现异常：{repr(e)}。正在第{i}次重启。')
            send(f'【main】错误！main()出现异常：{repr(e)}。正在第{i}次重启。',[],config,'debug',debug_group_chat)
            i += 1
            await asyncio.sleep(3)


if __name__ == '__main__':
    logger.info('程序正在启动')
    asyncio.run(main())