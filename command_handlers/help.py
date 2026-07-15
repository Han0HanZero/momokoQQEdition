from command_handlers.core import register_command
from main import COMMANDS

@register_command('help')
def get_help(t,d):
    response = ('欢迎使用桃桃子QQ版！\n'
                '只有使用有效的指令（以斜杠开头），桃桃子才会正确响应。\n'
                '如果在群聊中，你必须先@桃桃子。\n'
                '可用指令列表：')
    for key in COMMANDS.keys():
        response += '\n/' + key
    return [],response