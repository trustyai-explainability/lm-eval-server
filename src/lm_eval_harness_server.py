import os
import sys
import shlex

from fastapi import HTTPException
from typing import Dict
from src.api import *

from fastapi import APIRouter
import subprocess
import logging


logger = logging.getLogger(__name__)
router = APIRouter()


# === Registry of running lm-eval-harness jobs =====================================================
class LMEvalJob:
    def __init__(self, process, argument):
        self.process = process
        self.argument = argument
        self.cumulative_out = []
        self.cumulative_err = []
        self.progress = 0
running_processes : Dict[int, LMEvalJob] = {}  # track all currently running jobs


# === HELPERS ======================================================================================
def convert_to_cli(request: LMEvalRequest):
    """Convert an LMEvalRequest json object into an lm-eval cli argument"""
    args = get_lm_eval_arguments()  # grab the cli argument spec to translate json to cli

    cli_cmd = request.lm_eval_path
    for field in request.model_fields_set:
        if field in NON_CLI_ARGUMENTS:
            continue

        cli_cmd += " "
        arg = args[field]
        if arg['argparse_type'] in {"_StoreTrueAction", "_StoreFalseAction"}:
            cli_cmd += args[field]['cli']
        else:
            field_value = getattr(request, field)
            field_value = shlex.quote(field_value) if isinstance(field_value, str) else field_value
            cli_cmd += f"{args[field]['cli']} {field_value}"

    return cli_cmd


def _get_job_status(job):
    """Poll a running subprocess for exit codes"""
    status_code = job.process.poll()
    if status_code == 0:
        status = "Completed"
    elif status_code is None:
       status = "Running"
    else:
        status = "Error"

    return status, status_code


# === API ==========================================================================================
@router.post("/job", summary="Launch an lm-evaluation-harness job")
def lm_eval_job(request: LMEvalRequest):
    """Launch an lm-evaluation-harness job according to the inbound arguments. These
    match the CLI arguments to lm-evaluation-harness, just in json form."""

    # convert the json to cli arguments
    cli_cmd = convert_to_cli(request)

    logger.debug(f"Running command:       {cli_cmd}")
    logger.debug(f"Environment variables: {request.env_vars}")


    # todo: make sure you can't inject commands here
    p = subprocess.Popen(shlex.split(cli_cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    os.set_blocking(p.stdout.fileno(), False)
    os.set_blocking(p.stderr.fileno(), False)

    # register the subprocess in the global registry
    running_processes[p.pid] = LMEvalJob(p, cli_cmd)

    return {"status": "success", "job_pid": p.pid}



@router.get("/jobs", summary="List all running jobs")
def list_running_lm_eval_jobs(include_finished: bool=True) -> AllLMEvalJobs:
    """Provide a list of all lm-evaluation-harness jobs with attached summary information"""

    jobs = []
    for pid, job in running_processes.items():
        job_information = check_lm_eval_job(pid)

        if not include_finished and job_information.exit_code is not None:
            continue
        jobs.append(LMEvalJobSummary(**job_information.model_dump(exclude={"stdout", "stderr"})))

    return AllLMEvalJobs(jobs=jobs)


@router.get("/job/{pid}", summary="Get information about a specific job")
def check_lm_eval_job(pid: int) -> LMEvalJobDetail:
    """Get detailed report of an lm-evaluation-harness job by PID"""

    if pid not in running_processes:
        raise HTTPException(status_code=400, detail=f"No lm-evaluation-harness job with PID={pid} found.")

    job = running_processes[pid]
    status, status_code = _get_job_status(job)

    job.cumulative_out += [line for line in job.process.stdout]
    job.cumulative_err += [line for line in job.process.stderr]

    progress = 0
    for line in reversed(job.cumulative_err):
        if line.startswith("Requesting API:"):
            progress = int(line.split("Requesting API:")[1].split("%")[0].strip())
            break
    job.progress = progress
    return LMEvalJobDetail(
        pid=pid,
        argument=job.argument,
        status=status,
        exit_code=status_code,
        inference_progress_pct=job.progress,
        stdout=job.cumulative_out,
        stderr=job.cumulative_err
    )


@router.delete("/job/{pid}", summary="Delete an lm-evaluation-harness job's data from the server.")
def delete_lm_eval_job(pid: int):
    """Delete an lm-evaluation-harness job's data from the server by PID, terminating the job if it's still running"""
    if pid not in running_processes:
        raise HTTPException(status_code=400, detail=f"No lm-evaluation-harness job with PID={pid} found.")

    stop_lm_eval_job(pid)
    del running_processes[pid]
    return {"status": "success", "message": f"Job {pid} deleted successfully."}


@router.get("/job/{pid}/stop", summary="Stop a running lm-evaluation-harness job.")
def stop_lm_eval_job(pid: int):
    """Terminate an lm-evaluation-harness job by PID"""

    if pid not in running_processes:
        raise HTTPException(status_code=400, detail=f"No lm-evaluation-harness job with PID={pid} found.")

    job = running_processes[pid]

    if job.process.poll() is None:
        job.process.terminate()
        return {"status": "success", "message": f"Job {pid} terminated successfully."}
    else:
        return {"status": "success", "message": f"Job {pid} has already completed."}



