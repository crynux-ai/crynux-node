def env_vars_to_cmd_str(env_vars):
    cmd = "export"
    for var in env_vars.keys():

        if isinstance(env_vars[var], int):
            value = str(env_vars[var])
        else:
            value = '"' + env_vars[var] + '"'

        cmd = cmd + " " + var + '=' + value

    return cmd
