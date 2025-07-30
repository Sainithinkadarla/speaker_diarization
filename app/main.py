from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
import httpx
import os
from dotenv import load_dotenv
from csv import writer
import uuid
import aiofiles

load_dotenv()

app = FastAPI()

upload_dir = "uploaded_files"
csv_dir = "csv_files"
os.makedirs("uploaded_files", exist_ok=True)
os.makedirs(csv_dir,exist_ok=True)

@app.get("/")
def home():
    return {"Message": "Welcome to Speaker diarization API\n Go to /docs to use api"}

@app.post("/transcribe_diarize", summary="Transcription with Assembly AI and speaker diarization with pyannote")
async def get_transcribe(file: UploadFile = File()):
    user_id = uuid.uuid4()
    base_url = "https://api.assemblyai.com"

    headers = {
    "authorization": f"{os.getenv("AAI_KEY")}"
    }
    if not file.filename:
        raise HTTPException(status_code=400, detail= "No File Selected")
    
    file_extension = os.path.splitext(file.filename)[1]
    unique_filename = f"{user_id}{file_extension}"
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
            
            
            csv_filepath = os.path.join(csv_dir, f"{user_id}.csv")
            try:
                print("wrting csv")
                async with aiofiles.open(csv_filepath, "w", encoding="utf-8", newline="") as csv_file:
                    csv_writer = writer(csv_file)
                    await csv_writer.writerow(["word", "start", "end"])
                    for result in transcription_result["words"]:
                        await csv_writer.writerow([result["text"], result["start"], result["end"]])
                    print("csv written")
                return FileResponse(path= csv_filepath, 
                                    media_type="text/csv",
                                    filename="transcript.csv")
            except Exception as e:
                raise HTTPException(status_code= 500, detail= f"Failed to create csv file: {e}")


        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to process: {e}")
        finally:
            os.remove(filepath)
            print("audio file removed")
            file.file.close()
            # os.remove(csv_filepath)

@app.post("/diarize", summary="Speaker Diarization completely using Assembly AI ")
async def diarize(file: UploadFile = File()):
    user_id = uuid.uuid4()
    base_url = "https://api.assemblyai.com"

    headers = {
    "authorization": f"{os.getenv("AAI_KEY")}"
    }
    if not file.filename:
        raise HTTPException(status_code= 400, detail= "No File selected") 
    
    file_extension = os.path.splitext(file.filename)[1]
    filepath = os.path.join(upload_dir, f"{user_id}{file_extension}")
    try: 
        async with aiofiles.open(filepath, "wb") as buffer:
            while True:
                chunk = await file.read(8192)
                if not chunk:
                    break
                await buffer.write(chunk)

    except Exception as e:
        raise HTTPException(status_code= 500, detail = f"Could not save file to  disk {e}")

    async with httpx.AsyncClient() as client:
        try:
            async with aiofiles.open(filepath, "rb") as audio_file:
                audio = await audio_file.read()
                try:
                    response = await client.post(base_url+"/v2/upload", headers= headers, data = audio)
                    upload_url = response.json()['upload_url']
                except Exception as e:
                    raise HTTPException(status_code=500, detail = "Failed to get upload url from assembly ai")
                try:
                    data = {"audio_url": upload_url,
                        "speech_model": "universal"}
                    transcribe_url = base_url+"/v2/transcript"
                    response = await client.post(transcribe_url, json=data, headers=headers)
                    transcription_id = response.json()['id']
                except Exception as e:
                    raise HTTPException(status_code=500, detail="Failed to fetch transcription id")
                try:
                    polling_endpoint = f"{transcribe_url}/{transcription_id}"


                    while True:
                        transcription_response = await client.get(polling_endpoint, headers=headers)
                        transcription_result = transcription_response.json()
                        if transcription_result["status"] == "completed":
                            print("Finished speaker diarization")
                            break
                        if transcription_result["status"] == "error":
                            raise HTTPException(status_code=500, detail= f"Failed to {transcription_result["error"]}")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=e)
                
                csv_filepath = os.path.join(csv_dir, f"{user_id}.csv")
                try:
                    async with aiofiles.open(csv_filepath, "w", encoding="utf-8", newline="") as csvfile:
                        csv_writer = writer(csvfile)
                        await csv_writer.writerow(["word", "start", "end", "speaker"])
                        for result in transcription_result["words"]:
                            await csv_writer.writerow([result["text"], result["start"], result["end"], result["speaker"]])
                    return FileResponse(path= csv_filepath,
                                        media_type="text/csv",
                                        filename="diarizied transcript.csv")
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to create csv file {e}")


        except Exception as e:
            raise HTTPException(status_code=500, detail= f"Failed to fetch the transcript {e}")
        
        finally:
             os.remove(filepath)
             file.file.close()
