import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRecorder
import tempfile
import pyttsx3
import whisper
from marketing_agency.agent import root_agent  # your agent

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
pcs = set()

# Load Whisper model once
model = whisper.load_model("base")

class VoiceTrack(MediaStreamTrack):
    kind = "audio"
    def __init__(self, track):
        super().__init__()
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        return frame

@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    recorder = MediaRecorder(tempfile.NamedTemporaryFile(suffix=".wav").name)

    @pc.on("track")
    async def on_track(track):
        if track.kind == "audio":
            recorder.addTrack(track)
            await recorder.start()

            # Stop after 3 seconds for demo
            await asyncio.sleep(3)
            await recorder.stop()

            # Transcribe audio to text
            result = model.transcribe(recorder._path)
            text = result["text"]
            print("User said:", text)

            # Send to agent
            response = await root_agent.chat(text)
            print("Agent response:", response)

            # Convert response to audio
            engine = pyttsx3.init()
            engine.save_to_file(response, recorder._path.replace(".wav", "_out.wav"))
            engine.runAndWait()

            # TODO: play back _out.wav to user (requires proper MediaStreamTrack)
    
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}

@app.get("/")
async def index():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())

@app.on_event("shutdown")
async def shutdown_event():
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
