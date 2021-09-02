#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess

from snakemake.utils import read_job_properties
from datetime import date
import fcntl
from time import sleep
from functools import partial

default_queue_times = {
    "hotel": "24:00:00",
    "gpu-hotel": "24:00:00",
    "pdafm": "24:00:00",
    "home": "72:00:00",
    "condo": "8:00:00",
    "gpu-condo": "8:00:00",
    "glean": "1:00:00",
}
user_name = os.getlogin()
scratch_directory = f"/oasis/tscc/scratch/{user_name}"
log_directory = f"{scratch_directory}/TORQUE/logs/{date.today()}"
SLEEP_TIME = 1  # wait one second between job submission

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument(
    "--depend", help="Space separated list of ids for jobs this job should depend on."
)
parser.add_argument(
    "-a", help="Declare the time when the job becomes eligible for execution."
)
parser.add_argument("-A", help="Define the account string.")
parser.add_argument("-b", help="PBS Server timeout.")
parser.add_argument("-c", help="Checkpoint options.")
parser.add_argument("-C", help="Directive prefix in script file.")
parser.add_argument(
    "-d", help="Working directory to be used (default: ~). PBS_O_INITDIR"
)
parser.add_argument("-D", help="Root directory to be used. PBS_O_ROOTDIR")
parser.add_argument("-e", help="standard error path.", default=log_directory)
parser.add_argument("-f", help="Fault tolerant.", action="store_true")
parser.add_argument(
    "-h", help="Apply user hold at submission time", action="store_true"
)
parser.add_argument("-j", help="Merge standard error and standard out. (oe or eo)")
parser.add_argument("-l", help="Resource list.")
parser.add_argument("-m", help="Mail options.", default="a")
parser.add_argument("-M", help="Mail users.", default="{{cookiecutter.email}}")
parser.add_argument("-N", help="Name for the job.")
parser.add_argument("-o", help="standard output path.", default="/dev/null")
parser.add_argument("-p", help="Set job priority.")
parser.add_argument("-P", help="Proxy user for job.")
parser.add_argument("-q", help="Set destination queue.", default="condo")
parser.add_argument("-t", help="Array request.")
parser.add_argument("-u", help="Set user name for job.")
parser.add_argument("-v", help="Environment variables to export to the job.")
parser.add_argument("-V", help="Export all environment variables.", action="store_true")
parser.add_argument("-w", help="Set working directory. PBS_O_WORKDIR")
parser.add_argument(
    "-W", help="Additional attributes.", default="umask=0022"
)  # make logs readable by group
parser.add_argument("--help", help="Display help message.", action="store_true")

parser.add_argument("positional", action="append", nargs="?")
args = parser.parse_args()
if (args.e == log_directory or args.o == log_directory) and not os.path.isdir(
    log_directory
):
    os.makedirs(log_directory)

if args.help:
    parser.print_help()
    sys.exit(0)

jobscript = sys.argv[-1]

job_properties = read_job_properties(jobscript)

parameters = []
args_dict = vars(args)

nodes = ""
ppn = ""
mem = ""
walltime = ""
if "threads" in job_properties:
    ppn = f"ppn={job_properties['threads']}"
if "resources" in job_properties:
    resources = job_properties["resources"]
    if "nodes" in resources:
        nodes = f"nodes={resources['nodes']}"
    if ppn and not nodes:
        nodes = "nodes=1"
    if "mem" in resources:
        mem = f"mem={resources['mem']}"
    if "walltime" in resources:
        walltime = f"walltime={resources['walltime']}"
    if "queue" in resources and "-q" not in sys.argv:
        args_dict["q"] = str(resources["queue"])
    if "email" in resources and not args_dict["M"]:
        args_dict["M"] = str(resources["email"])
    if "mail" in resources and not args_dict["m"]:
        args_dict["m"] = str(resources["mail"])
if "params" in job_properties:
    params = job_properties["params"]
    if "stdout" in params:
        if not args_dict["o"]:
            os.makedirs(os.path.dirname(params["stdout"]), exist_ok=True)
            args_dict["o"] = params["stdout"]
    if "stderr" in params:
        if not args_dict["e"]:
            os.makedirs(os.path.dirname(params["stderr"]), exist_ok=True)
            args_dict["e"] = params["stderr"]


def format_argument(args_dict, arg, quote_argument=False):
    if args_dict[arg]:
        if type(args_dict[arg]) is bool:
            return f"-{arg}"
        else:
            if quote_argument:
                return f'-{arg} "{args_dict[arg]}"'
            else:
                return f"-{arg} {args_dict[arg]}"
    else:
        return ""


format_argument = partial(format_argument, args_dict)
for arg in (
    "a",
    "A",
    "c",
    "C",
    "d",
    "D",
    "e",
    "f",
    "h",
    "j",
    "l",
    "m",
    "M",
    "o",
    "p",
    "P",
    "q",
    "t",
    "u",
    "v",
    "w",
):
    parameter = format_argument(arg)
    if parameter:
        parameters.append(parameter)
for arg in ("W",):
    parameter = format_argument(arg, quote_argument=True)
    if parameter:
        parameters.append(parameter)
jname = ""
if args.N:
    jname = f"-N {args_dict['N']}"
else:
    if "wildcards" in job_properties:
        jname = "-N {wildcards}.{rule}".format(
            wildcards=".".join(iter(job_properties["wildcards"].values())),
            rule=job_properties["rule"],
        )
    elif "groupid" in job_properties:
        jname = f"-N {job_properties['groupid']}"
parameters.append(jname)

parameters.append("-V")
if args.depend:
    parameters.append(f' -W "depend=afterok:{args.depend.replace(" ", ":")}"')
if args.positional:
    parameters.append(f' {" ".join(args.positional)}')

if not walltime:
    walltime = f"walltime={default_queue_times[args.q]}"

resourceparams_list = []
if nodes or ppn or mem or walltime:
    resourceparams_list.append('-l "')
    if nodes:
        resourceparams_list.append(nodes)
        if ppn:
            resourceparams_list.append(f":{ppn}")
        if mem:
            resourceparams_list.append(",")
    if mem:
        resourceparams_list.append(mem)
    if walltime:
        if nodes or mem:
            resourceparams_list.append(",")
        resourceparams_list.append(walltime)
    resourceparams_list.append('"')
    parameters.append("".join(resourceparams_list))

cmd = "qsub " + " ".join(parameters)

# write the command to a log file and wait for a second to avoid overwhelming
# the scheduler
class Locker:
    def __enter__(self):
        lock = f"{scratch_directory}/.snakemake.lock"
        if not os.path.isfile(lock):
            with open(lock, "w") as _:
                pass
        self.fp = open(lock)
        fcntl.fcntl(self.fp.fileno(), fcntl.LOCK_EX)

    def __exit__(self, _type, value, tb):
        fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
        self.fp.close()


with Locker():
    with open(f"{log_directory}/snakemake.qsub.log", "a") as qsub_log:
        qsub_log.write(f"{cmd}\n")
    sleep(SLEEP_TIME)

try:
    res = subprocess.run(cmd, capture_output=True, check=True, shell=True)
except subprocess.CalledProcessError as e:
    print(f"stdout was: {e.stdout}")
    print(f"stderr was: {e.stderr}")
    raise e

res = res.stdout.decode()
print(res.strip())
