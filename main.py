# ===== IMPORTS ======
import fastapi
import uvicorn
import subprocess
import shutil
import os
import pathlib
from fastapi.responses import FileResponse, JSONResponse
from fastapi import UploadFile, File, HTTPException


# ===== Create FastAPI App =====
app = fastapi.FastAPI()

# Define directories
INPUTS_DIR = pathlib.Path("inputs")
SCRIPT_PATH = "report_generator_react.py"

# Create the inputs directory if it doesn't exist
INPUTS_DIR.mkdir(exist_ok=True)

# ===== API ROUTES =====

@app.post("/scan/")
async def scan_iac_file(file: UploadFile = File(...)):
    """
    Endpoint to upload an IaC file for analysis.
    """
    
    # 1. Save the uploaded file to the 'inputs/' directory
    input_filepath = INPUTS_DIR / file.filename
    try:
        with input_filepath.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")
    finally:
        file.file.close()

    # 2. Run report_generator_react.py script
    try:
        # Run as subprocess
        process = subprocess.run(
            ["python", SCRIPT_PATH, str(input_filepath)],
            capture_output=True,  # Capture stdout and stderr
            text=True,
            check=False,          # Don't raise an error on non-zero exit
            timeout=300           # 5-minute timeout
        )

        # Handle script errors
        if process.returncode != 0:
            return JSONResponse(
                status_code=500,
                content={"error": "Analysis script failed", "stderr": process.stderr}
            )

        # 3. Find the report file path from the script's output
        stdout = process.stdout
        report_path = None
        for line in stdout.splitlines():
            if line.startswith("FINAL_REPORT_PATH:"):
                report_path = line.split("FINAL_REPORT_PATH:")[1].strip()
                break
        
        if not report_path or not os.path.exists(report_path):
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Script ran but backend could not find report path.",
                    "stdout": stdout
                }
            )

        # 4. Send the report JSON file back to the user
        return FileResponse(
            path=report_path,
            media_type="application/json",
            filename="security_report.json"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An error occurred: {e}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)