from command_handlers.core import register_command
from loguru import logger
import json
from main import get_chat_config, instantiate_chats, Chat, GroupChat, C2CChat

@register_command('register')
def register(t:str, d:dict) -> tuple[list, str]:
    content = d['content']
    details:list = content.split(' ')
    i = 0
    for word in details:
        if word.startswith('/'):
            break
        i += 1
    details = details[i+1:]
    if len(details) < 1:
        return [], '缺少参数，执行/register help查看帮助。'
    if details[0] == 'help':
        return [], ('/register 帮助\n'
                    '- 单聊环境：\n'
                    '  - 使用/register user [用户名(字符串)] [所在地纬度(整数或小数)] [所在地经度(整数或小数)]来把自己注册进单聊列表中。其中，[用户名]不得带有空格，[所在地纬度]北正南负，[所在地经度]东正西负。\n'
                    '    示例：/register user 郑昊宇 39.9 114.4\n'
                    '    这个命令将把位于北京的命令发送者郑昊宇注册进单聊列表。\n'
                    '- 群聊环境：\n'
                    '  - 使用/register group [群名称(字符串)]来把当前群聊注册进群聊列表中。其中，[群名称]不得带有空格。群成员【只有】执行这个命令后，【才】能把自己注册进群聊的成员列表。\n'
                    '    示例：/register group 郑昊宇迫害协会\n'
                    '    这个命令将把当前群聊注册进群聊列表中，名称将为“郑昊宇迫害协会”。群成员【只有】执行这个命令后，【才】能把自己注册进群聊的成员列表。\n'
                    '  - 使用/register user [用户名(字符串)] [所在地纬度(整数或小数)] [所在地经度(整数或小数)]来把自己注册进群聊的成员列表中。其中，[用户名]不得带有空格，[所在地纬度]北正南负，[所在地经度]东正西负。执行这个命令前，【必须】先把群聊注册进群聊列表。\n'
                    '    示例：/register user 郑昊宇 39.9 114.4\n'
                    '    这个命令将把位于北京的命令发送者郑昊宇注册进群聊的成员列表中。执行这个命令前，【必须】先把群聊注册进群聊列表。\n'
                    '- 如果已经注册过，再次执行该命令将覆盖之前注册的信息。\n'
                    '- 执行/register help以再次查看此帮助。')
    chat_config = get_chat_config()
    i = 0
    if t == 'C2C_MESSAGE_CREATE':  # 单聊环境
        if len(details) < 4:
            return [], '缺少参数，执行/register help查看帮助。'
        if details[0] != 'user':
            return [], '命令的第二部分无效！'
        try:
            new_user_config = {
                'openid': d['author']['user_openid'],
                'name': details[1],
                'location': [float(details[2]),float(details[3])]
            }
        except Exception as e:
            return [], f'尝试生成新config时失败：{repr(e)}'
        is_c2c_existed = False
        for user in chat_config['c2c_users']:  # 检查当前单聊是否存在
            if d['author']['user_openid'] == user['openid']:
                is_c2c_existed = True
                logger.info('当前单聊存在')
                chat_config['c2c_users'][i] = new_user_config  # 存在，覆盖
                break
            i += 1
        if not is_c2c_existed:
            logger.info('当前单聊不存在')
            chat_config['c2c_users'].append(new_user_config)  # 不存在，追加
    elif t == 'GROUP_MESSAGE_CREATE':  # 群聊环境
        is_group_existed = False
        for group in chat_config['groups']:  # 检查当前群聊是否存在
            if d['group_openid'] == group['openid']:
                is_group_existed = True
                logger.info('当前群聊存在')
                break  # 存在，继续
            i += 1
        if not is_group_existed and details[0] != 'group':  # 不存在也不注册，报错
            logger.warning('当前群聊未注册！')
            return [], '当前群聊未注册！'
        if details[0] == 'user':  # 存在，准备注册成员
            if len(details) < 4:
                return [], '缺少参数，执行/register help查看帮助。'
            if float(details[2]) > 90.0 or float(details[2]) < -90.0 or float(details[3]) > 180.0 or float(details[3]) < -180.0:
                return [], ('坐标不合法！纬度取值范围[-90,90]，东正西负；经度取值范围[-180,180]，北正南负。先写纬度，后写经度。\n'
                            '参考值：北京(39.9,116.4)；承德(41.0,118.0)；衡水(37.7,115.7)')
            i_member = 0
            logger.info('准备注册成员')
            try:
                new_member_config = {
                    'openid': d['author']['member_openid'],
                    'name': details[1],
                    'location': [float(details[2]),float(details[3])]
                }
            except Exception as e:
                return [], f'尝试生成新config时失败：{repr(e)}'
            is_member_existed = False
            for member in group['members']:  # 检查成员是否存在
                if d['author']['member_openid'] == member['openid']:
                    logger.info('当前成员存在，覆盖')
                    is_member_existed = True
                    chat_config['groups'][i]['members'][i_member] = new_member_config  # 存在，覆盖
                    break
                i_member += 1
            if not is_member_existed:
                logger.info('当前成员不存在，追加')
                chat_config['groups'][i]['members'].append(new_member_config)  # 不存在，追加
        elif details[0] == 'group':  # 无论存不存在，准备注册群聊
            logger.info('准备注册群聊')
            if len(details) < 2:
                return [], '缺少参数，执行/register help查看帮助。'
            try:
                new_group_config = {
                    'openid': d['group_openid'],
                    'name': details[1],
                    'members': []
                }
            except Exception as e:
                return [], f'尝试生成新config时失败：{repr(e)}'
            if is_group_existed:
                logger.info('当前群聊存在，覆盖')
                chat_config['groups'][i]['name'] = new_group_config['name']  # 存在，覆盖
            else:
                logger.info('当前群聊不存在，追加')
                chat_config['groups'].append(new_group_config)  # 不存在，追加
    else:
        return [], '事件类型错误！'
    try:
        with open('./chat_config.json', 'w') as f:
            logger.info('正在打开chat_config.json')
            f.write(json.dumps(chat_config, indent=2))
    except Exception as e:
        logger.error(f'写入文件时出错：{repr(e)}')
    else:
        logger.success('写入文件成功')
    return [], '已写入文件。'