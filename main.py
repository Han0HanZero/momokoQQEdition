import asyncio
import websockets
import json
from haversine import haversine
import math
import requests
from time import sleep


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
    def __init__(self, user:dict):
        self.name = user[0]
        self.id = user[1]
        self.latitude = user[2]
        self.longitude = user[3]
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


def get_config() -> dict:
    try:
        with open('config.json','r') as f:
            config = json.load(f)
            return config
    except FileNotFoundError:
        print('错误：config.json不存在！')
        exit()
    except Exception as e:
        print(f'错误：{repr(e)}')
    return config


def send(response:str, affected_users:list, config:dict) -> bool:
    print(response)
    i = 1
    while i <= 3:  # 获取access_token
        try:
            access_token = requests.post('https://bots.qq.com/app/getAppAccessToken', json={
                'appId': str(config['app_id']),
                'clientSecret': config['secret']
            }).json()['access_token']
        except Exception as e:
            print(f'警告！获取access token失败：{repr(e)}。这是第{i}次尝试。')
            if i >= 3:
                print('发送失败')
                return False
            else:
                sleep(3)
                i += 1
        else:
            break
    i = 1
    while i <= 3:  # 发送消息
        try:
            result = requests.post(f'https://api.sgroup.qq.com/v2/groups/{config["target_open_id"]}/messages',
                                   json={'content': response,
                                         'msg_type': 0},
                                   headers={
                                       'Authorization': f'QQBot {access_token}'
                                       ''
                                   })
            result.raise_for_status()
        except Exception as e:
            print(f'警告！发送消息失败：{repr(e)}。这是第{i}次尝试。')
            if i >= 3:
                print('发送失败')
                return False
            else:
                sleep(3)
                i += 1
        else:
            print(f'发送消息成功！')
            return True


def instantiate_users(config:dict) -> list:
    users = []
    try:
        for user_config in config['users']:
            users.append(User(user_config))
        return users
    except Exception as e:
        print('错误：实例化用户失败。')
        send('致命错误：实例化用户失败，检查config。',[],config)
        exit()


async def get_eew(uri:str, config:dict):
    users = instantiate_users(config)
    async with websockets.connect(uri) as websocket:
        print('成功建立连接，等待......')
        send('成功连接服务器！',[],config)
        async for reception in websocket:
            print('接收！'+str(reception))
            is_send = False
            affected_users = []
            reception_dic = json.loads(reception)
            if reception_dic['type'] == 'heartbeat':
                print('是心跳包')
                continue
            else:
                print('是EEW')
                eew = Eew(reception_dic)
                for user in users:
                    user.calc_local_intensity(eew)
                    if user.local_intensity < config['threshold_intensity']:
                        continue
                    else:
                        is_send = True
                        affected_users.append(user)
                if is_send:
                    response = f'⚠️即时地震信息⚠️\n{eew.origin_time}，{eew.hypo_center}发生了{str(eew.magnitude)}级地震，震源深度{str(eew.depth)}km，预估最大烈度{eew.max_intensity}。\n注意，以下群友可能受到影响：\n'
                    sorted_affected_users = sorted(affected_users, key=lambda u: u.local_intensity, reverse=True)
                    for user in sorted_affected_users:
                        response += f'{user.level} {user.name} - 预估烈度{str(round(user.local_intensity))}\n'
                    response += "请立即避险！\n伏地·遮挡·手抓牢"
                    send(response, affected_users, config)


async def main():
    config = get_config()
    uri = config['eew_source']
    i = 1
    while i<=10:
        try:
            await get_eew(uri,config)
            i = 1
        except Exception as e:
            print(f'错误！{repr(e)}。这是第{i}次尝试。')
            send(f'错误！{repr(e)}。这是第{i}次尝试。',[],config)
            i += 1
            sleep(5)
    print('Fatal！main停止')
    send('注意：发生致命错误，主进程已停止运行！',[],config)


if __name__ == '__main__':
    asyncio.run(main())