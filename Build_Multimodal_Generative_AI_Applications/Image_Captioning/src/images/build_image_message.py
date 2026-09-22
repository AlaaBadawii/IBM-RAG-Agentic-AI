"""Build a multimodal message for an image."""


def build_image_message(image_data_url: str, question: str) -> list:
    """Build a multimodal chat message with text and image_url content parts."""
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": question},
                {"type": "image_url", "image_url": {"url": image_data_url}},
            ],
        }
    ]
