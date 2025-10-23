from datetime import datetime
import json
from templates import SecurityReport
import os

# ===== Graph Node Functions =====

def get_file(state: dict) -> dict:
    """
    This node takes the file path and gets the IaC code.
    """

    print("Fetching code...")
    path = state["file_path"]

    try:
        with open(path, "r", encoding="utf-8") as f:
            iac_code = f.read()
    except FileNotFoundError:
        print(f"Error: File not found at {path}")
        iac_code = ""
    except Exception as e:
        print(f"Error reading file: {e}")
        iac_code = ""

    return {"iac_template": iac_code}


def generate_report_issues(state: dict, llm, prompt_template) -> dict:
    """
    This node calls the LLM to check and document all the issues in an IaC Template
    """

    if(state["iac_template"] == ""):
        return {"iac_issues" : []}

    print("Analyzing IaC Template...")
    iac_template = state["iac_template"]
    chain = prompt_template | llm
    ai_report = chain.invoke({"iac_template": iac_template})
    print("Report Scanned")
    return {"iac_issues": ai_report}
    

def populate_metadata(state: dict) -> dict:
    """
    This node populates the other fields of the SecuirtyReport Class
    """ 
    print("Generating Report Metadata...")
    # Extract issues from AI output
    issues = state.get("iac_issues", [])
    issues = issues.issues

    # Generate report name (FileName + Timestamp)
    file_name = state.get("file_path", "unknown_file").split("/")[-1]
    file_name = file_name.replace(".", "_")
    timestamp = datetime.now()
    name = f"{file_name}_{timestamp.strftime('%Y-%m-%d_%H:%M:%S')}"

    # Compute summary
    summary = {
        "count": len(issues),
        "low": sum(1 for i in issues if i.severity == "Low"),
        "medium": sum(1 for i in issues if i.severity == "Medium"),
        "high": sum(1 for i in issues if i.severity == "High"),
    }

    # Populate state
    state["name"] = name
    state["summary"] = summary
    state["timestamp"] = timestamp
    state["file"] = state.get("file_path", "unknown_file")

    final_report = SecurityReport(
        name=name,
        summary=summary,
        timestamp=timestamp,
        file=state.get("file_path", "unknown_file"),
        issues=issues
    )
    
    print("Metadata Populated")

    return {"report": final_report}


def save_results(state: dict):

    print("Generated Report:\n")
    report = json.dumps(state["report"].model_dump(), indent=2, default=str)
    print(report)

    output_file_path = f"./outputs/{state["report"].name}.json"
    os.makedirs("./outputs", exist_ok=True)
    with open(output_file_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {output_file_path}")
