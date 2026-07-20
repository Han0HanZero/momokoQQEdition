import asyncio
import websockets
import json
from haversine import haversine
import math
import requests
from loguru import logger
import os
import importlib

from websockets import ConnectionClosedError

from command_handlers.core import COMMANDS, RegisterError


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
    """
    未使用
    """
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


def import_handlers():
    try:
        logger.info('正在查找命令处理器。')
        files = os.listdir('./command_handlers')
        i = 0
        success_count = 0
        for file in files:
            if file.endswith('.py') and file != '__init__.py' and file != 'core.py' and file != 'example.py':
                i += 1
                logger.info(f'准备加载第{i}个命令处理器：{file}。')
                try:
                    importlib.import_module(f'command_handlers.{file[:-3]}')
                except RegisterError as e:
                    logger.error(f'加载命令处理器{file[:-3]}时出错（命令冲突：{repr(e)}），此处理器的加载已被跳过。')
                except Exception as e:
                    logger.error(f'加载命令处理器{file[:-3]}时出错（{repr(e)}），此处理器的加载已被跳过。')
                else:
                    logger.success(f'成功加载命令处理器：{file[:-3]}。')
                    success_count += 1
            else:
                logger.info(f'已经跳过：{file}。')
        logger.success(f'成功加载{success_count}/{i}个命令处理器。')
    except Exception as e:
        logger.error(f'加载命令处理器时遇到问题：{repr(e)}。')


def get_config() -> dict:
    try:
        with open('config.json','r') as f:
            config = json.load(f)
            logger.success('配置获取成功。')
            logger.info(config)
            return config
    except FileNotFoundError:
        logger.critical('获取配置时遇到问题：config.json不存在！')
        exit(-1)
    except Exception as e:
        logger.error(f'获取配置时遇到问题：{repr(e)}。')
    if not config:
        logger.critical('配置获取失败。')
        exit(-1)
    return config


def get_chat_config() -> dict:
    try:
        with open('chat_config.json','r') as f:
            chat_config = json.load(f)
            logger.success('会话配置获取成功。')
            logger.info(chat_config)
            return chat_config
    except FileNotFoundError:
        logger.critical('获取会话配置时遇到问题：chat_config.json不存在！')
        exit(-1)
    except Exception as e:
        logger.error(f'获取会话配置时遇到问题：{repr(e)}。')
    if not chat_config:
        logger.critical('会话配置获取失败。')
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
            logger.error(f'获取access token失败：{repr(e)}。这是第{i}次尝试。')
            if i >= 5:
                logger.error('获取access token失败。')
                return None
            else:
                i += 1
                continue
        else:
            return access_token


def send(response:str, mentioned_users:list|str, config:dict, msg_type:str, target:C2CChat|GroupChat) -> bool:
    logger.info(f'准备发送：{response}，目标为{target.name}（{target.openid}）。')
    access_token = get_access_token(config)
    if type(target) == C2CChat:
        target_type = 'users'
    elif type(target) == GroupChat:
        target_type = 'groups'
    else:
        logger.error('传入send函数的target类型不明。')
        return False
    i = 1
    while i <= 5:  # 发送消息
        try:
            result = requests.post(f'https://api.sgroup.qq.com/v2/{target_type}/{target.openid}/messages',
                                   json={'content': response,
                                         'msg_type': 0},
                                   headers={
                                       'Authorization': f'QQBot {access_token}'
                                   })
            result.raise_for_status()
        except Exception as e:
            logger.error(f'警告！发送消息失败：{repr(e)}。这是第{i}次尝试。')
            if i >= 5:
                logger.error('发送消息失败。')
                return False
            else:
                i += 1
        else:
            logger.success(f'发送消息成功！')
            return True


def instantiate_chats(chat_config:dict) -> list[GroupChat|C2CChat]:
    logger.info('正在实例化会话。')
    try:
        chats = []
        for group_config in chat_config['groups']:
            group = GroupChat(group_config)
            chats.append(group)
        for user_config in chat_config['c2c_users']:
            c2c_user = C2CChat(user_config)
            chats.append(c2c_user)
        logger.success('会话实例化成功。')
        return chats
    except Exception as e:
        logger.critical(f'会话实例化失败（{repr(e)}，请手动重启。')


def instantiate_debug_group_chat(chat_config:dict) -> GroupChat:
    try:
        debug_group = GroupChat(chat_config['debug_group'])
    except Exception as e:
        logger.critical('Debug会话实例化失败，请手动重启。')
        exit(-1)
    return debug_group


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
        if i > 1000:
            logger.critical('重试次数太多，进程已终止，请手动重启。')
            send('连接Wolfx Open API时重试次数太多，进程已终止，请手动重启。',[],config,'debug',debug_group_chat)
            exit(-1)
        try:
            async with websockets.connect(uri) as websocket:
                logger.success('成功连接Wolfx Open API，等待......')
                send('成功连接Wolfx Open API！',[],config,'debug',debug_group_chat)
                i = 1
                async for reception in websocket:  # 处理收到的包
                    logger.info('从Wolfx Open API收到：'+str(reception))
                    is_send = False
                    reception_dic = json.loads(reception)
                    if reception_dic['type'] == 'heartbeat':
                        logger.info('从Wolfx Open API收到的包是一个心跳包。')
                        try:
                            await websocket.send('ping')
                            logger.success('成功向Wolfx Open API发送ping包。')
                        except Exception as e:
                            logger.error(f'向Wolfx Open API发送ping包失败：{repr(e)}。')
                        continue
                    elif reception_dic['type'] == 'pong':
                        logger.success('成功自Wolfx Open API接收到pong包。')
                        continue
                    elif reception_dic['type'] == 'cenc_eew':
                        logger.info('从Wolfx Open API收到的包是一个EEW包。')
                        eew = Eew(reception_dic)
                        chat_config = get_chat_config()
                        chats = instantiate_chats(chat_config)
                        logger.info('重载了EEW的会话列表。')
                        for chat in chats:  # 逐对话计算烈度
                            affected_users = []
                            is_send = False
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
                                    if user.local_intensity < 1.0:
                                        user.local_intensity = 1.0
                                    response += f'{user.level} {user.name} - 预估烈度{str(round(user.local_intensity,1))}\n'
                                response += "请立即避险！\n伏地·遮挡·手抓牢"
                                send(response, affected_users, config,'text',chat)  # 最终发送
                            else:
                                pass
                    elif reception_dic['type'] == 'cenc_eqlist':
                        logger.info('从Wolfx Open API收到的包是一个地震情报包。')
                        continue
                    else:
                        logger.warning('从Wolfx Open API收到的包的类型不在预期内。')
                        send(f'从Wolfx Open API收到的包的类型不在预期内：{reception_dic["type"]}。',[],config,'debug',debug_group_chat)
        except ConnectionClosedError:
            logger.error(f'与Wolfx Open API的连接断开，正在重新连接。这是第{i}次尝试。')
            if i == 1 or i % 10 == 0:
                send(f'与Wolfx Open API的连接断开，正在重新连接。这是第{i}次尝试。',[],config,'debug',debug_group_chat)
            i += 1
            await asyncio.sleep(3)
        except TimeoutError as e:
            logger.error(f'尝试与Wolfx Open API连接时超时：{repr(e)}。这是第{i}次尝试。')
            if i == 1 or i % 10 == 0:
                send(f'尝试与Wolfx Open API连接时超时：{repr(e)}。这是第{i}次尝试。',[],config,'debug',debug_group_chat)
            i += 1
        except Exception as e:
            logger.error(f'与Wolfx Open API连接时出现未知错误：{repr(e)}。这是第{i}次尝试。')
            if i == 1 or i % 10 == 0:
                send(f'与Wolfx Open API连接时出现未知错误：{repr(e)}。这是第{i}次尝试。',[],config,'debug',debug_group_chat)
            i += 1


async def heartbeat(websocket, heartbeat_interval:int, state:dict):
    while True:
        try:
            await asyncio.sleep(heartbeat_interval)
            await websocket.send(json.dumps({'op': 1, "d": state['latest_s']}))
            logger.success('成功向QQ后台发送心跳包。')
        except ConnectionClosedError as e:
            #state['is_reconnect'] = True
            logger.error(f'向QQ后台发送心跳包失败，服务端可能在要求resume：{repr(e)}。')
        except Exception as e:
            logger.error(f'向QQ后台发送心跳包失败：{repr(e)}。')



async def listen(config:dict, state:dict, chat_config:dict) -> None:
    access_token = get_access_token(config)
    chats = instantiate_chats(chat_config)
    debug_group_chat = instantiate_debug_group_chat(chat_config)
    i = 1
    while True:
        try:
            uri = requests.get('https://api.sgroup.qq.com/gateway', headers={'Authorization': f'QQBot {access_token}'}).json()['url']
        except Exception as e:
            if i > 50:
                logger.critical('从QQ后台获取网关地址失败，请手动重启程序。')
                send('从QQ后台获取网关地址失败，请手动重启程序。',[],config,'debug',debug_group_chat)
                exit(-1)
            logger.error(f'从QQ后台获取网关地址失败:{repr(e)}。这是第{i}次尝试。')
            if i == 1 or i % 10 == 0:
                send(f'从QQ后台获取网关地址失败。这是第{i}次尝试。',[],config,'debug',debug_group_chat)
            i += 1
        else:
            logger.success(f'从QQ后台获取网关地址成功：{uri}。')
            break
    i = 1
    connected = False
    resumed = False
    while True:
        if i > 100:  # 监听启动失败
            logger.critical('对QQ后台的监听启动失败，请手动重启。')
            send('对QQ后台的监听启动失败，请手动重启。',[],config,'debug',debug_group_chat)
            exit(-1)
        try:
            access_token = get_access_token(config)
            async with websockets.connect(uri) as websocket:  # 尝试连接事件服务器
                logger.success('成功连接QQ后台！')
                if resumed:
                    resumed = False
                else:
                    send('成功连接QQ后台！',[],config,'debug',debug_group_chat)
                if not connected:  # 首次连接的话，尝试接受一个Hello包，发送一个Identify，并启动心跳协程
                    hello = json.loads(await websocket.recv())  # 接收Hello
                    logger.info(hello)
                    if hello['op'] == 10:  # 处理第一个包
                        logger.success(f'从QQ后台收到Hello包，要求的interval为{hello["d"]["heartbeat_interval"]}。')
                        heartbeat_interval = hello['d']['heartbeat_interval'] / 1000 * 0.99
                        connected = True
                    else:
                        logger.critical(f'从QQ后台收到的Hello包不正常，其op为{hello["op"]}')
                        send(f'从QQ后台收到的Hello包异常（{hello["op"]}），请手动重启。', [], config, 'debug',debug_group_chat)
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
                        logger.success('向QQ后台鉴权成功，监听开始。')
                        i = 1
                        state['latest_s'] = ready['s']
                        session_id = ready['d']['session_id']
                        connected = True
                        heartbeat_task = asyncio.create_task(heartbeat(websocket, heartbeat_interval, state))
                    else:
                        logger.critical('向QQ后台鉴权失败，监听启动失败，请手动重启。')
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
                    try:
                        heartbeat_task.cancel()
                        await heartbeat_task
                    except asyncio.CancelledError:
                        heartbeat_task = asyncio.create_task(heartbeat(websocket, heartbeat_interval, state))
                    resumed = True
                # ===== 以上为连接部分 =====
                # ===== 事件处理 =====
                async for event in websocket:
                    logger.info('从QQ后台收到事件：'+event+'。')
                    event = json.loads(event)
                    op = event['op']
                    if op == 0:  # 消息推送
                        if event['t'] == 'GROUP_MESSAGE_CREATE' or event['t'] == 'C2C_MESSAGE_CREATE':  # 判断是不是消息
                            logger.info('从QQ后台收到消息。')
                            if_mentioned = False
                            if event['t'] == 'C2C_MESSAGE_CREATE':  # 只有私聊或者被@时消息才会被分配给handler
                                logger.info('消息是单聊，处理。')
                                if_mentioned = True
                            else:
                                if not event['d'].get('mentions'):
                                    logger.info('消息是群聊，但未提到任何人，不处理。')
                                    continue
                                for mentioned_user in event['d']['mentions']:
                                    if mentioned_user['is_you']:
                                        if_mentioned = True
                                        break
                            if not if_mentioned:
                                logger.info('消息是群聊，但未被提到，不处理。')
                                continue
                            content = event['d']['content']
                            for word in content.split(' '):
                                if not word.startswith('/'):  # 只有以/开头的部分可以被识别为命令并分配给handler
                                    continue
                                else:
                                    logger.info('发现“/”。')
                                    command = word.removeprefix('/')
                                    if COMMANDS.get(command) is None:
                                        logger.error(f'命令{command}不存在。')
                                        mentioned_users, response = [], f'命令{command}不存在！'
                                    else:
                                        try:
                                            mentioned_users, response = COMMANDS[command](event['t'], event['d'])  # 分发命令并获取响应
                                            if command == 'register':
                                                chat_config = get_chat_config()
                                                chats = instantiate_chats(chat_config)
                                                logger.info('由于命令关键字是register，重载了监听的会话列表。')
                                        except Exception as e:
                                            logger.error(f'处理命令时发生问题：{repr(e)}。')
                                            response = f'处理命令时发生问题：{repr(e)}。'
                                            mentioned_users = []
                                    target = None
                                    for chat in chats:
                                        if event['t'] == 'C2C_MESSAGE_CREATE' and event['d']['author']['user_openid'] == chat.openid:
                                            target = chat
                                            break
                                        elif event['t'] == 'GROUP_MESSAGE_CREATE' and event['d'].get('group_openid') == chat.openid:
                                            target = chat
                                            break
                                        else:
                                            pass
                                    if not target:
                                        if event['t'] == 'C2C_MESSAGE_CREATE':
                                            user_config = {
                                                'openid': event['d']['author']['user_openid'],
                                                'name': event['d']['author']['username'],
                                                'location': [0,0]
                                            }
                                            target = C2CChat(user_config)
                                            response += '\nℹ 您的单聊会话尚未注册，请尽早注册。发送/register help查看帮助。'
                                        elif event['t'] == 'GROUP_MESSAGE_CREATE':
                                            group_config = {
                                                'openid': event['d'].get('group_openid'),
                                                'name': '',
                                                'members': []
                                            }
                                            target = GroupChat(group_config)
                                            response += '\nℹ 您的群聊会话尚未注册，请尽早注册。发送/register help查看帮助。'
                                        else:
                                            pass
                                    logger.info('目标：'+target.openid)
                                    send(response,mentioned_users,config,'debug',target)
                                    break


                    elif op == 1:  # 心跳
                        logger.warning('QQ后台似乎发送了一个心跳包？')
                        pass
                    elif op == 7:  # 需要重连
                        logger.error('QQ后台要求重新连接。')
                        break
                    elif op == 9:  # session无效
                        logger.error('QQ后台称session无效。')
                        connected = False
                        break
                    elif op == 10:  # Hello
                        logger.warning('QQ后台似乎发送了一个Hello包。')
                        pass
                    elif op == 11:  # 心跳ack
                        logger.info('收到QQ后台的心跳ack。')
                        pass
                    else:
                        logger.error('从QQ后台收到了OpCode无法识别的包，请检查。')
                        pass
        except ConnectionClosedError:
            logger.error('与QQ后台连接中断。')
            send('与QQ后台连接中断。',[],config,'debug',debug_group_chat)


async def main():
    config = get_config()
    chat_config = get_chat_config()
    debug_group_chat = instantiate_debug_group_chat(chat_config)
    import_handlers()
    logger.info(f'注册表如下：{COMMANDS}')
    #is_send_debug = config['is_send_debug']
    state = {'latest_s': None, 'is_reconnect': False}
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
            logger.error(f'main()出现异常：{repr(e)}。正在第{i}次重启。')
            send(f'main()出现异常：{repr(e)}。正在第{i}次重启。',[],config,'debug',debug_group_chat)
            i += 1
            await asyncio.sleep(3)


if __name__ == '__main__':
    logger.add("./logs/bot.log", rotation="1 day", retention="7 days", enqueue=True)
    logger.info('----------------')
    logger.info('桃桃子QQ版')
    logger.info('MOMOKO QQ Edition')
    logger.info('(C) HanZero from HANICE Network Technology Studio')
    logger.info('Available on https://github.com/Han0HanZero/momokoQQEdition. Distributed under MIT License.')
    logger.info('----------------')
    logger.info('程序正在启动。')
    asyncio.run(main())