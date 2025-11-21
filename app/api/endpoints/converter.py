"""AI file conversion endpoints"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pathlib import Path
import tempfile
from app.services.file_converter import FileConverter

router = APIRouter(prefix="/api", tags=["converter"])

@router.post("/convert")
async def convert_file(
    file: UploadFile = File(...),
    record_type: str = Form("auto")
):
    """Convert CSV/Excel/TXT file to JSON using AI"""

    # Validate file type
    allowed_extensions = ['.csv', '.xlsx', '.xls', '.txt']
    file_extension = Path(file.filename).suffix.lower()

    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        # Convert using AI
        converter = FileConverter()
        result = converter.convert_file(tmp_path, record_type)

        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Conversion failed: {str(e)}"
        )

    finally:
        # Clean up temp file
        if tmp_path.exists():
            tmp_path.unlink()
