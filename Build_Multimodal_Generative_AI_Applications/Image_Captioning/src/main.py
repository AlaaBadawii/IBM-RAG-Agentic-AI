"""Entry point for the Image Captioning application."""
import argparse
import logging
import sys

from src.images.loader import InvalidImageError
from src.services.vision import VisionService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def main():
    parser = argparse.ArgumentParser(description="Multimodal Image Understanding")
    parser.add_argument("--image", required=True, help="Path to image file")
    parser.add_argument("--task", default="caption", help="Task: caption, question, counting, extraction, assessment")
    parser.add_argument("--question", default="", help="Question for question/counting/extraction tasks")
    parser.add_argument("--model", default=None, help="Override model name for switching")
    parser.add_argument("--compare", action="store_true", help="Compare primary and fallback models")
    args = parser.parse_args()

    try:
        service = VisionService(model_name=args.model)

        if args.compare:
            results = service.compare_models(args.image, args.question or "Describe the image.")
            for model_name, result in results.items():
                print(f"\n=== {model_name} ===")
                print(result.text)
            return

        result = _route_task(service, args.task, args.image, args.question)
        print(result.text)
    except InvalidImageError as e:
        print(f"Image error: {e}")


def _route_task(service: VisionService, task: str, image: str, question: str):
    """Route the task to the correct service method."""
    if task == "caption":
        return service.caption_image(image)
    elif task == "question":
        return service.answer_image_question(image, question)
    elif task == "assessment":
        return service.assess_image(image)
    elif task == "counting":
        return service.count_objects(image, question)
    elif task == "extraction":
        return service.extract_information(image, question)
    else:
        print(f"Unknown task: {task}. Use: caption, question, counting, extraction, assessment")
        sys.exit(1)


if __name__ == "__main__":
    main()
