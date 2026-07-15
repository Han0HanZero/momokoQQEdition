COMMANDS = {}

class RegisterError(Exception):
    pass

def register_command(command:str):
    def decorator(func):
        if COMMANDS.get(command) is None:
            COMMANDS[command] = func
        else:
            raise RegisterError(f'Command {command} has been assigned to {COMMANDS[command].__name__}.')
        return func
    return decorator
