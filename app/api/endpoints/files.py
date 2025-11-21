"""File management endpoints"""
from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from pathlib import Path
import json
import shutil
from typing import List

router = APIRouter(prefix="/api", tags=["files"])

SAMPLE_DATA_DIR = Path("sample_data")

@router.get("/files")
async def list_files():
    """List all JSON files in sample_data/"""
    if not SAMPLE_DATA_DIR.exists():
        return []

    files = []
    for file_path in SAMPLE_DATA_DIR.glob("*.json"):
        try:
            with open(file_path) as f:
                data = json.load(f)
                files.append({
                    "name": file_path.name,
                    "records": len(data.get("records", [])),
                    "type": infer_record_type(file_path.name)
                })
        except:
            pass

    return files


@router.get("/files/{filename}")
async def get_file(filename: str):
    """Get file contents"""
    file_path = SAMPLE_DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    with open(file_path) as f:
        return json.load(f)


@router.get("/files/{filename}/download")
async def download_file(filename: str):
    """Download file"""
    file_path = SAMPLE_DATA_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(file_path, filename=filename)


@router.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a file to sample_data/ - automatically converts CSV/XLSX/TXT to JSON using AI"""
    import tempfile
    from app.services.file_converter import FileConverter

    SAMPLE_DATA_DIR.mkdir(exist_ok=True)

    # Check file type
    file_extension = Path(file.filename).suffix.lower()

    # If it's already JSON, just validate and save
    if file_extension == '.json':
        file_path = SAMPLE_DATA_DIR / file.filename
        with open(file_path, 'wb') as f:
            shutil.copyfileobj(file.file, f)

        # Validate JSON
        try:
            with open(file_path) as f:
                data = json.load(f)
                if "records" not in data:
                    raise HTTPException(status_code=400, detail="Invalid format: missing 'records' key")
        except json.JSONDecodeError:
            file_path.unlink()
            raise HTTPException(status_code=400, detail="Invalid JSON file")

        return {
            "message": "File uploaded successfully",
            "filename": file.filename,
            "converted": False
        }

    # For CSV/XLSX/TXT - convert using AI
    if file_extension not in ['.csv', '.xlsx', '.txt']:
        raise HTTPException(
            status_code=400,
            detail="Only JSON, CSV, XLSX, and TXT files are supported"
        )

    # Save to temp file with original filename
    temp_dir = Path(tempfile.gettempdir())
    temp_filename = f"upload_{file.filename}"
    tmp_path = temp_dir / temp_filename

    content = await file.read()
    with open(tmp_path, 'wb') as f:
        f.write(content)

    try:
        # Convert using AI
        converter = FileConverter()
        result = converter.convert_file(tmp_path, record_type="auto")

        # Save converted JSON
        json_filename = Path(file.filename).stem + ".json"
        file_path = SAMPLE_DATA_DIR / json_filename

        with open(file_path, 'w') as f:
            json.dump(result, f, indent=2)

        return {
            "message": f"File converted and saved as {json_filename}",
            "filename": json_filename,
            "converted": True,
            "record_type": result.get("record_type", "unknown"),
            "records_count": len(result.get("records", []))
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI conversion failed: {str(e)}"
        )
    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()


@router.delete("/files/{filename}")
async def delete_file(filename: str):
    """Delete a file"""
    file_path = SAMPLE_DATA_DIR / filename

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    return {"message": "File deleted successfully"}


def infer_record_type(filename: str) -> str:
    """Infer record type from filename"""
    filename_lower = filename.lower()
    if "natural" in filename_lower:
        return "naturalization"
    elif "immig" in filename_lower:
        return "immigration"
    elif "census" in filename_lower:
        return "census"
    elif "obit" in filename_lower:
        return "obituary"
    elif "birth" in filename_lower:
        return "birth"
    return "unknown"
