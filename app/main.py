from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
import httpx
import os
from dotenv import load_dotenv
from csv import writer
import uuid
import shutil
import aiofiles

load_dotenv()

app = FastAPI()

upload_dir = "uploaded_files"
csv_dir = "csv_files"
os.makedirs("uploaded_files", exist_ok=True)
os.makedirs(csv_dir,exist_ok=True)

@app.post("/transcribe")
async def get_transcribe(file: UploadFile = File()):
    base_url = "https://api.assemblyai.com"

    headers = {
    "authorization": f"{os.getenv("AAI_KEY")}"
    }
    if not file.filename:
        raise HTTPException(status_code=400, detail= "No File Selected")
    
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    filepath = os.path.join(upload_dir, unique_filename)
    try:
        async with aiofiles.open(filepath, "wb") as buffer:
            while True:
                chunk = await file.read(8192)
                if not chunk:
                    break
                await buffer.write(chunk)
    except Exception as e:
        print(f"Error uploading the file: {e}")
        raise HTTPException(status_code= 500, detail= f"Could not upload file: {e}")

    async with httpx.AsyncClient() as client:

        try:
            async with aiofiles.open(filepath, "rb") as audio_file:
                audio = await audio_file.read()
                response = await client.post(base_url+"/v2/upload", headers= headers, data = audio)

            upload_url = response.json()["upload_url"]
            print(upload_url)
            data = {"audio_url": upload_url,
                    "speech_model":"universal"}
            transcribe_url = base_url+"/v2/transcript"
            response = await client.post(transcribe_url, json = data, headers=headers)

            polling_endpoint = transcribe_url + f"/{response.json()['id']}"

            while True:
                transcription_response = await client.get(polling_endpoint, headers=headers)
                transcription_result = transcription_response.json()
                if transcription_result["status"] == "completed":
                    print("Finished transcribing")
                    break
                if transcription_result["status"] == "error":
                    raise HTTPException(status_code= 500,detail = f"Transcription failed: {transcription_result["error"]}")
            
            
            csv_filepath = os.path.join(csv_dir, f"{unique_filename}.csv")
            try:
                async with aiofiles.open(csv_filepath, "w", encoding="utf-8", newline="") as csv_file:
                    csv_writer = writer(csv_file)
                    csv_writer.writerow(["word", "start", "end"])
                    for result in transcription_result["words"]:
                        await csv_writer.writerow([result["text"], result["start"], result["end"]])

                return FileResponse(path= csv_filepath, 
                                    media_type="text/csv",
                                    filename="transcript.csv")
            except Exception as e:
                raise HTTPException(status_code= 500, detail= f"Failed to create csv file: {e}")


        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process: {e}")
        finally:
            os.remove(filepath)
            file.file.close()