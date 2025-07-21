from fastapi import FastAPI, UploadFile, File, HTTPException
from typing import List
import shutil
import os
import uuid # For generating unique filenames

app = FastAPI()

# Directory to save uploaded files
UPLOAD_DIR = "uploaded_files"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
async def root():
    return {"message": "Visit /uploadfile or /uploadmultiplefiles to upload files."}

@app.post("/uploadfile/")
async def create_upload_file(
    # Use UploadFile type hint, and File() as the dependency
    # 'file' here will correspond to the field name in the form data
    file: UploadFile = File(...)
):
    """
    Uploads a single file.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected")

    # Securely generate a unique filename
    # You might want to sanitize file.filename further in a real app
    # For now, we'll just append a UUID to prevent collisions
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)

    try:
        # Open the file in binary write mode
        # Use shutil.copyfileobj for efficient streaming
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "file_size": file.size, # Note: file.size might be None until read in some cases
            "saved_as": unique_filename,
            "message": "File uploaded successfully!"
        }
    except Exception as e:
        # Log the error for debugging
        print(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Could not upload file: {e}")
    finally:
        # Ensure the UploadFile object is closed
        # This is usually handled by FastAPI, but good practice if you manually
        # consume its content or pass it around.
        file.file.close()


@app.post("/uploadmultiplefiles/")
async def create_upload_files(
    # For multiple files, use List[UploadFile]
    files: List[UploadFile] = File(...)
):
    """
    Uploads multiple files.
    """
    uploaded_info = []
    for file in files:
        if not file.filename:
            # This case shouldn't typically happen if the client sends a proper multi-part form
            continue # Skip empty file entries

        file_extension = os.path.splitext(file.filename)[1]
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        try:
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            uploaded_info.append({
                "filename": file.filename,
                "content_type": file.content_type,
                "file_size": file.size,
                "saved_as": unique_filename,
                "status": "success"
            })
        except Exception as e:
            uploaded_info.append({
                "filename": file.filename,
                "status": "failed",
                "error": str(e)
            })
        finally:
            file.file.close()
            
    if not uploaded_info:
        raise HTTPException(status_code=400, detail="No files were uploaded or selected.")

    return {"uploaded_files": uploaded_info}


# To run this API:
# uvicorn main:app --reload