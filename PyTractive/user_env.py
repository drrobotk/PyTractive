"""
Module to interact with the user environment variables.

Provides the functions:

*func*: `user_environ`
*func*: `add_user_environment`
"""
import platform
if platform.system() == 'Windows':
    import winreg

def user_environ(key: str) -> str:
    """
    Get the value of a user environment variable.

    Args:
        key: str
            The name of the environment variable.
    Returns:
        str
            The value of the environment variable.
    """
    try:
        reg_key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment')
        return winreg.QueryValueEx(reg_key, key)[0]
    except:
        return False

def add_user_environment(
    key: str, 
    value: str
) -> None:
    """
    Add a user environment variable.

    Args:
        key: str
            The name of the environment variable.
        value: str
            The value of the environment variable.
    Returns:
        None
    """
    # This is for the system run variable
    reg_key = winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, 'Environment', 0, winreg.KEY_SET_VALUE
    )

    with reg_key:
        if value is None:
            winreg.DeleteValue(reg_key, key)
        else:
            if '%' in value:
                var_type = winreg.REG_EXPAND_SZ
            else:
                var_type = winreg.REG_SZ
            winreg.SetValueEx(reg_key, key, 0, var_type, value)
