from command_handlers.core import register_command

@register_command('命令关键词')  # 使用这个注册器将函数注册进COMMANDS，传入注册器的参数为命令的关键词，即/后，第一个空格前的部分。关键词不得存在空格。
def example_func(t:str, d:dict):
    """
    如果用户发送的命令关键词与上方注册器传入的参数相同，程序就会将消息分配给此函数处理。会传入两个参数：t和d（解释见https://bot.q.qq.com/wiki/develop/api-v2/dev-prepare/interface-framework/event-emit.html和https://bot.q.qq.com/wiki/develop/api-v2/server-inter/message/send-receive/event.html）。
    :param t: 事件类型。应当为'C2C_MESSAGE_CREATE'（单聊消息）或'GROUP_MESSAGE_CREATE'（群聊消息）。
    :param d: 事件详情。包含发送者信息、群聊信息（若有）、被@的用户、消息内容、时间戳等信息。
    :return: 需要返回一个列表和一个字符串，列表为需在回复中@的用户（若为单聊则返回空列表[]），字符串为要回复的内容。
    """
    return ['user_openid_1', 'user_openid_2'], '要回复的内容'