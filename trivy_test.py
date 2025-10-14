import subprocess

file_path = "main.tf"  # replace with your IaC file

try:
    result = subprocess.run(
        ["trivy", "config", file_path, "--quiet"],
        capture_output=True,
        text=True,
        check=False
    )
    print("Trivy scan output:")
    print(result.stdout or "No issues found")
except FileNotFoundError:
    print("Trivy not installed or not in PATH")
except Exception as e:
    print(f"Error running Trivy: {e}")
