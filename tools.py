from langchain.tools import ToolRuntime
from langchain_core.tools import tool

from pydantic import BaseModel, Field

import subprocess
import json
import os

# ===== Agent Tools =====

# class CheckovToolArgs(BaseModel):
#     input_file_path: str = Field(description="File Path to the IaC Code File to be checked.")

@tool
def checkov_tool(input_file_path: str, output_dir: str, output_file_name: str) -> str:
    """
    Runs a Checkov static analysis scan on a local IaC file path.
    Use this tool to find security misconfigurations in Terraform,
    CloudFormation, Kubernetes, Dockerfiles, or other IaC files.
    
    This tool performs two actions:
    1. Saves the full JSON report to a file in the './checkov_logs' directory.
    2. Returns the same JSON report to the agent.

    Args:
    input_file_path: File Path to the IaC Code File to be checked.
    output_dir: Directory where checkov output file will be stored.
    output_file_name: Desired name of the checkov output file.
    """

    # FIX LATER: USE GRAPH STATE TO GET RUNTIME CONTEXT INSTEAD OF PASSING IT TO LLM
    # output_dir = runtime.state["output_dir"]
    # output_file_name = runtime.state["output_file_name"]

    try:
        # Run Checkov
        subprocess.run(
            ["checkov", "-f", input_file_path, "-o", "json", "--output-file-path", output_dir],
            check=False
        )

        # Read checkov output
        with open(output_dir + "results_json.json", "r", encoding="utf-8") as f:
            data = json.load(f)

        # Only consider failed checks
        failed_checks = data.get("results", {}).get("failed_checks", [])

        # Only consider a subset of information for each failed check
        final_json = [
            {
                "check_id": c.get("check_id"),
                "bc_check_id": c.get("bc_check_id"),
                "check_name": c.get("check_name"),
                "file_line_range": c.get("file_line_range"),
                "resource": c.get("resource"),
                "guideline": c.get("guideline"),
            }
            for c in failed_checks
        ]

        # Final tool output
        final_json_str = json.dumps(final_json, indent=2, default=str)

        # Write the changes
        with open(output_dir + "results_json.json", "w", encoding="utf-8") as f:
            f.write(final_json_str)

        # Rename the file
        new_name = output_dir + "checkov_" + output_file_name + ".json"
        os.rename(output_dir + "results_json.json", new_name)

        return final_json_str

    except Exception as e:
        print("Checkov Tool failed to run.")
        print(e)
        return ""