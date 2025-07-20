from fastapi import FastAPI, File, UploadFile
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from rembg import new_session, remove
from PIL import Image
import io
import asyncio
import numpy as np
import cv2
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

rembg_session = new_session("u2net")
executor = ThreadPoolExecutor()
MAX_IMAGE_SIZE = (1024, 1024)

def process_image(image_bytes: bytes) -> bytes:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    img.thumbnail(MAX_IMAGE_SIZE)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)

    result_bytes = remove(buf.read(), session=rembg_session)

    result_img = Image.open(io.BytesIO(result_bytes)).convert("RGBA")
    result_np = np.array(result_img)

    b, g, r, a = cv2.split(result_np)
    a = cv2.GaussianBlur(a, (7, 7), 0)
    a[a < 10] = 0
    smoothed_np = cv2.merge((b, g, r, a))

    final_img = Image.fromarray(smoothed_np, mode='RGBA')
    cleaned_buffer = io.BytesIO()
    final_img.save(cleaned_buffer, format="PNG")
    cleaned_buffer.seek(0)
    return cleaned_buffer.read()

@app.get("/")
def health():
    return {"status": "ok"}

@app.post("/remove-background")
async def remove_background(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        return JSONResponse(status_code=400, content={"error": "Please upload a valid image."})

    try:
        image_bytes = await file.read()
        loop = asyncio.get_event_loop()
        output_bytes = await loop.run_in_executor(executor, process_image, image_bytes)

        return StreamingResponse(
            io.BytesIO(output_bytes),
            media_type="image/png",
            headers={"Content-Disposition": "inline; filename=removed-bg.png"}
        )
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Processing failed: {str(e)}"})

# Optional if running locally
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080)
