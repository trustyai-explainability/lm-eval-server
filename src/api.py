import json
from enum import Enum
import sys
from typing import Optional, List, Dict
from lm_eval.__main__ import setup_parser as lm_eval_setup_parser


from pydantic import BaseModel, create_model


# ===  JOB STATUSES =================================================================================
class JobStatus(Enum):
    RUNNING = "Running"
    FAILED = "Failed"
    COMPLETED = "Completed"
    QUEUED = "Queued"
    STOPPED = "Stopped"


# === STATIC API OBJECTS ===========================================================================
class LMEvalJobSummary(BaseModel):
    job_id: int
    argument: str
    status: JobStatus
    timestamp: Optional[str]
    exit_code: Optional[int]
    inference_progress_pct: int


class LMEvalJobDetail(LMEvalJobSummary):
    stdout: List[str]
    stderr: List[str]


class AllLMEvalJobs(BaseModel):
    jobs: List[LMEvalJobSummary]



# === Dynamic API Object from LM-Eval CLI ==========================================================
NON_CLI_ARGUMENTS = {
    "env_vars": (Dict[str, str], {}),
    "lm_eval_path": (str, f"{sys.executable} -m lm_eval")
}

def get_lm_eval_arguments():
    """Grab all fields from an argparse specification into a dictionary"""
    parser = lm_eval_setup_parser()  # grab lm-eval argparse specification

    args = {}
    for action in parser._positionals._actions:
        arg = {"cli": action.option_strings[0], "argparse_type":action.__class__.__name__}
        if action.__class__.__name__ == "_StoreTrueAction":
            arg["type"] = bool
            arg["default"] = False
        elif action.__class__.__name__ == "_StoreFalseAction":
            arg["type"] = bool
            arg["default"] = True
        elif action.__class__.__name__ == "_HelpAction":
            continue
        else:
            arg["default"] = action.default
            arg["type"] = str if action.type == str.upper else action.type
        args[action.dest] = arg
    return args


def get_model():
    """Build a Pydantic model from the lm-eval argparse arguments, adding in a few config variables of our own as well"""
    args = get_lm_eval_arguments()
    model_args = {k:(v['type'],v['default']) for k,v in args.items()}
    model_args.update(NON_CLI_ARGUMENTS)
    return create_model("LMEvalRequest", **model_args)

# Dynamically create the lm-eval-harness job request from the library's argparse
LMEvalRequest = get_model()


if __name__ == "__main__":
    with open("LMEvalRequest_schema.json", "w") as f:
        f.write(json.dumps(LMEvalRequest.model_json_schema()))
