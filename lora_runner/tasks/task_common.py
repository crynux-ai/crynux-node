import os


def env_vars_to_cmd_str(env_vars):
    cmd = "export"
    for var in env_vars.keys():

        if isinstance(env_vars[var], int):
            value = str(env_vars[var])
        else:
            value = '"' + env_vars[var] + '"'

        cmd = cmd + " " + var + '=' + value

    return cmd


def print_cuda_info(log_file):
    cmd = "cd /app/lora-scripts && python ./gpu_info.py"
    cmd = cmd + ' >> "' + log_file + '" 2>&1'

    status = os.system(cmd)

    if os.WIFEXITED(status):
        if os.WEXITSTATUS(status) != 0:
            raise Exception("training process exited with error")
    else:
        raise Exception("training process did not exit normally")
