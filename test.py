# instantiate the pipeline
from dotenv import load_dotenv
import os
load_dotenv()

HF_KEY = os.getenv("HF_KEY")
from pyannote.audio import Pipeline
pipeline = Pipeline.from_pretrained(
  "pyannote/speaker-diarization-3.1",
  use_auth_token=HF_KEY)

# run the pipeline on an audio file
with open("Transcription/Case 07_converted.wav", "rb") as f:
    diarization = pipeline(f)#, num_speakers=2)
    # diarization = pipeline(f, num_speakers=2)


# dump the diarization output to disk using RTTM format
with open("audio.rttm", "w") as rttm:
    diarization.write_rttm(rttm)
    
