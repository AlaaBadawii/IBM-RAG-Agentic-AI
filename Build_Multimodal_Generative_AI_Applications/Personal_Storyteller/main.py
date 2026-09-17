import io
import os
import tempfile

import gradio as gr
import requests
from dotenv import load_dotenv
from gtts import gTTS

load_dotenv()

OPENROUTER_API_KEY = os.getenv("LLM_API_KEY")
BASE_URL = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
MODEL_ID = os.getenv("LLM_MODEL", "meta-llama/llama-4-maverick-17b-128e-instruct")

def generate_story(topic):
    prompt = f"""Write an engaging and educational story about {topic} for beginners.
            Use simple and clear language to explain basic concepts.
            Include interesting facts and keep it friendly and encouraging.
            The story should be around 200-300 words and end with a brief summary of what we learned.
            Make it perfect for someone just starting to learn about this topic."""

    response = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": MODEL_ID,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 2500,
        },
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]

def process(topic):
    story = generate_story(topic)
    tts = gTTS(story)
    audio_path = os.path.join(tempfile.gettempdir(), "story_audio.mp3")
    tts.save(audio_path)
    return story, audio_path

demo = gr.Interface(
    fn=process,
    inputs=gr.Textbox(lines=2, placeholder="Enter a topic, e.g. the life cycle of butterflies"),
    outputs=[
        gr.Textbox(label="Story"),
        gr.Audio(label="Listen to the story", autoplay=True),
    ],
    title="Personal Storyteller",
    description="Enter a topic to generate an educational story and listen to it!",
)

if __name__ == "__main__":
    demo.launch(share=True)
