"""Gradio interface for the Vision service."""
import gradio as gr
from src.services.vision import VisionService

service = VisionService()


def caption_image(image):
    if image is None:
        return ""
    result = service.caption_image(image)
    return result.text


def ask_question(image, question):
    if image is None or not question:
        return ""
    result = service.answer_image_question(image, question)
    return result.text


def count_objects(image, object_name):
    if image is None or not object_name:
        return ""
    result = service.count_objects(image, object_name)
    return result.text


def create_gallery():
    iface = gr.Blocks(title="Multimodal Vision App")
    with iface:
        gr.Markdown("# Multimodal Image Understanding")
        with gr.Tabs():
            with gr.TabItem("Caption"):
                image_input = gr.Image(type="filepath")
                btn1 = gr.Button("Caption")
                output1 = gr.Textbox()
                btn1.click(caption_image, inputs=image_input, outputs=output1)
            with gr.TabItem("Question"):
                image_input2 = gr.Image(type="filepath")
                question_input = gr.Textbox(placeholder="Ask a question...")
                btn2 = gr.Button("Answer")
                output2 = gr.Textbox()
                btn2.click(ask_question, inputs=[image_input2, question_input], outputs=output2)
            with gr.TabItem("Count"):
                image_input3 = gr.Image(type="filepath")
                object_input = gr.Textbox(placeholder="Object to count...")
                btn3 = gr.Button("Count")
                output3 = gr.Textbox()
                btn3.click(count_objects, inputs=[image_input3, object_input], outputs=output3)
    return iface


if __name__ == "__main__":
    create_gallery().launch()