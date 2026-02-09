import subprocess

def call_git(test_mode, *args, **kwargs):
    """
        wrapper for calls to git
        *args: one or more strings to be arguements to the git command
    """
    params=["git"]
    for i in args:
        if isinstance(i, list):
            params+=i
        else:
            params.append(i)

    if test_mode:
        print(" ".join(params))
        return ""
    print(" ".join(params))
    #subprocess.run(params, check=True)
    p = subprocess.Popen(params,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT)
    return p.stdout.read()


def call_gh(test_mode, *args, **kwargs):
    """
        wrapper for calls to git
        *args: one or more strings to be arguements to the git command
    """
    params=["gh"]
    for i in args:
        if isinstance(i, list):
            params+=i
        else:
            params.append(str(i))

    print(f"run {' '.join(params)}")
    if test_mode:
        return ""
    p = subprocess.Popen(params,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.STDOUT)

    return p.stdout.read()


def get_git_commit(version):
    try:
        submodule = call_git(False, "submodule", "status", f"release-{version.replace("-",".")}/kernel-module-management")
        return submodule.decode("utf-8").split(" ")[1]
    except Exception as e:
        print(e)
        return "unknown"

