"""FastAPI routes for the Vision service."""
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse

from src.services.vision import VisionService
from src.images.loader import InvalidImageError, SecurityError
from src.clients.openrouter import OpenRouterError
from src.exceptions import RetryExhaustedError

app = FastAPI(title="Multimodal Vision API")

service = VisionService()


@app.post("/v1/vision/caption")
async def caption(image: UploadFile = File(...)):
    """Generate a caption for the uploaded image."""
    try:
        contents = await image.read()
        result = service.caption_image(image.filename)
        return {"task": "caption", "answer": result.text, "model": result.model}
    except (InvalidImageError, SecurityError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RetryExhaustedError:
        raise HTTPException(status_code=503, detail="Service unavailable after retries")


@app.post("/v1/vision/question")
async def question(image: UploadFile = File(...), question: str = ""):
    """Answer a question about the uploaded image."""
    try:
        result = service.answer_image_question(image.filename, question)
        return {"task": "question", "answer": result.text, "model": result.model}
    except (InvalidImageError, SecurityError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RetryExhaustedError:
        raise HTTPException(status_code=503, detail="Service unavailable after retries")


@app.get("/v1/models")
async def list_models():
    """List available models."""
    from src.config import get_available_models
    return {"models": get_available_models()}