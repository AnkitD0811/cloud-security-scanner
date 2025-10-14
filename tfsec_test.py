import subprocess

file_path = "."  # replace with your IaC file

try:
    result = subprocess.run(
        ["tfsec", file_path, "--format", "json"],
        capture_output=True,
        text=True,
        check=False
    )
    print("tfsec scan output:")
    print(result.stdout or "No issues found")
except FileNotFoundError:
    print("tfsec not installed or not in PATH")
except Exception as e:
    print(f"Error running tfsec: {e}")
