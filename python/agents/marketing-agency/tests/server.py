import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRelay, MediaBlackhole
import json
from marketing_agency.agent import root_agent  # your ADK agent
from google.genai import Client

# Initialize ADK / Vertex AI client
client = Client(vertexai=True,
                project=os.getenv("GOOGLE_CLOUD_PROJECT"),
                location=os.getenv("GOOGLE_CLOUD_LOCATION"))

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


class VoiceTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track):
        super().__init__()  # initialize base
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        # Here you could process audio frame if you want STT
        return frame


pcs = set()

@app.post("/offer")
async def offer(request: Request):
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("track")
    async def on_track(track):
        print("Track received:", track.kind)
        if track.kind == "audio":
            local_track = VoiceTrack(track)
            # Optional: process audio frames with STT and feed to agent
            # For now, just discard
            pc.addTrack(local_track)

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
