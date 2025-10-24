import subprocess
import json
import os

# ===== Agent Tools =====

def checkov_tool(input_file_path: str, output_file_path: str):
    """
    Tool that runs checkov on a given file and stores the output json
    """
    
    try:
        # Run Checkov
        subprocess.run(
            ["checkov", "-f", input_file_path, "-o", "json", "--output-file-path", output_file_path]
        )

        # Read checkov output
        with open(output_file_path + "results_json.json", "r", encoding="utf-8") as f:
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

        # Write the changes
        with open(output_file_path + "results_json.json", "w", encoding="utf-8") as f:
            f.write(json.dumps(final_json, indent=2, default=str))

        # Rename the file
        new_name = "./outputs/Hello_World.json"
        os.rename(output_file_path + "results_json.json", new_name)

    except Exception as e:
        print("Checkov Tool failed to run.")
        print(e.stderr)
        return {}