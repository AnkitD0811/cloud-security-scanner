import os
import subprocess
import json
from google import genai
from google.genai import types

# =============================
# Environment Setup
# =============================
# Make sure your Gemini API key is set
# export GEMINI_API_KEY="YOUR_KEY"
client = genai.Client()

# =============================
# Define Tool Functions (Hands)
# =============================
def run_checkov(file_path: str) -> str:
    """Run Checkov and return findings."""
    try:
        result = subprocess.run(
            ["checkov", "-f", file_path, "-o", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout if result.stdout else "No issues found."
    except FileNotFoundError:
        return "Checkov not installed."
    except Exception as e:
        return f"Error: {e}"

def run_tfsec(file_path: str) -> str:
    """Run tfsec scan."""
    dir_path = file_path if os.path.isdir(file_path) else os.path.dirname(file_path)
    try:
        result = subprocess.run(
            ["tfsec", dir_path, "--format", "json"],
            capture_output=True,
            text=True,
            check=False,
        )
        return result.stdout if result.stdout else "No issues found."
    except FileNotFoundError:
        return "tfsec not installed."
    except Exception as e:
        return f"Error: {e}"

# Map tool names to functions
TOOL_MAP = {
    "checkov": run_checkov,
    "tfsec": run_tfsec,
}

# =============================
# Define Tool Declarations for Gemini
# =============================
tool_declarations = []
for tool_name in TOOL_MAP.keys():
    tool_declarations.append({
        "name": f"run_{tool_name}",
        "description": f"Run {tool_name} on a given IaC file path and return its output.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to IaC file"},
            },
            "required": ["file_path"]
        }
    })

tools = types.Tool(function_declarations=tool_declarations)
config = types.GenerateContentConfig(tools=[tools])

import re
import json


def extract_json_from_text(text: str):
    """
    Remove ```json ... ``` or ``` ... ``` fences from Gemini output.
    Returns Python dict.
    """
    if not text:
        return {}

    # Remove ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"```", "", text)
    text = text.strip()

    # Extract first JSON object
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception as e:
            print(f"❌ Failed to parse JSON: {e}")
            return {}
    return {}


# =============================
# Brain → Hands → Brain Agent
# =============================
def run_iac_agent(file_path: str):
    # Prepare report folder
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    report_folder = f"SecReports_{base_name}"
    os.makedirs(report_folder, exist_ok=True)

    # 1️⃣ Gemini decides which tools to run
    decision_prompt = f"""
    You are an IaC security expert. The file path is: {file_path}.
    Decide which of these tools to run for maximum coverage: checkov, tfsec.
    Return a JSON array called 'tools' with the names of the tools to run.
    """
    decision_resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=decision_prompt,
        config=config
    )

    # Extract tool decisions
    raw_text = decision_resp.candidates[0].content.parts[0].text or ""
    selected_tools = [t for t in TOOL_MAP.keys() if t in raw_text.lower()]
    if not selected_tools:
        selected_tools = list(TOOL_MAP.keys())  # fallback to all

    print(f"🛠️ Selected tools: {selected_tools}")

    # 2️⃣ Execute selected tools (Hands)
    tool_results = {}
    for tool_name in selected_tools:
        print(f"▶ Running {tool_name}...")
        output = TOOL_MAP[tool_name](file_path)
        # Save intermediate report
        report_path = os.path.join(report_folder, f"{tool_name}_report.json")
        try:
            # Attempt to pretty-print JSON
            parsed = json.loads(output)
            pretty_output = json.dumps(parsed, indent=2)
        except Exception:
            pretty_output = output
        with open(report_path, "w") as f:
            f.write(pretty_output)
        tool_results[tool_name] = pretty_output

    # 3️⃣ Gemini summarizes all results (Brain)
    results_text = ""
    for tool, output in tool_results.items():
        results_text += f"--- {tool.upper()} RESULTS ---\n{output}\n\n"

    summary_prompt = f"""
    You are an IaC security expert. Here are the scan results:

    {results_text}

Please return a JSON object with the following structure:

{{
    "severity": {{
        "critical": int,
        "high": int,
        "medium": int,
        "low": int,
        "passed": int
    }},
    "key_findings": [string],
    "recommendations": [string],
    "overall_security_posture": string
}}

Populate it accurately based on the scan results. Do not include extra text outside the JSON.
"""
    summary_resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=summary_prompt,
        config=config
    )

    # Extract summary text safely
    summary_text = ""
    for part in summary_resp.candidates[0].content.parts:
        if part.text:
            summary_text += part.text

    # Safe JSON extraction
    print(summary_text)
    structured_summary = extract_json_from_text(summary_text)

    # Save summary as JSON
    summary_file = os.path.join(report_folder, "final_summary.json")
    summary_data = {
        "file_scanned": file_path,
        "tools_used": selected_tools,
        "structured_summary": structured_summary
    }
    with open(summary_file, "w") as f:
        json.dump(summary_data, f, indent=2)

    print(f"\n💾 Reports saved in folder: {report_folder}")

# =============================
# Run Example
# =============================
if __name__ == "__main__":
    file_path = input("Enter path to Terraform (.tf) file: ").strip()
    run_iac_agent(file_path)
