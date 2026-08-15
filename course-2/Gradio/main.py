import gradio as gr
import requests
import torch
from torchvision import transforms
from transformers import BlipForConditionalGeneration


# Download human-readable labels for ImageNet
response = requests.get("https://git.io/JJkYN")
labels = [l.strip() for l in response.text.split("\n") if l.strip()]

# Define image preprocessing (IMPORTANT for ResNet)
transform = transforms.Compose(
    [
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ]
)
model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)


def predict(inp):
    # preprocess image
    inp = transform(inp).unsqueeze(0)

    # ensure model runs in inference mode
    with torch.no_grad():
        prediction = torch.nn.functional.softmax(model(inp)[0], dim=0)

    # map predictions to labels
    confidences = {labels[i]: float(prediction[i]) for i in range(len(labels))}

    return confidences


gr.Interface(
    fn=predict,
    inputs=gr.Image(type="pil"),
    outputs=gr.Label(num_top_classes=3),
    examples=[
        "https://www.bing.com/images/search?view=detailV2&ccid=wuKGLmwS&id=04C6E40108D58F2991AA28C4E9AFC96E2449D9D0&thid=OIP.wuKGLmwSrpJeNMYa9NX6KAHaE7&mediaurl=https%3a%2f%2fimages.pexels.com%2fphotos%2f7316511%2fpexels-photo-7316511.jpeg%3fcs%3dsrgb%26dl%3dpexels-zante-7316511.jpg%26fm%3djpg&cdnurl=https%3a%2f%2fth.bing.com%2fth%2fid%2fR.c2e2862e6c12ae925e34c61af4d5fa28%3frik%3d0NlJJG7Jr%252bnEKA%26pid%3dImgRaw%26r%3d0&exph=4039&expw=6059&q=running+dog+in+a+beach&mode=overlay&FORM=IQFRBA&ck=7E1BE7406BC0EA6523408C49F5C383E1&selectedIndex=0&idpp=serp",
        "https://th.bing.com/th/id/OIP.FWZRIDjkV2nxuFJZ9OXv9wHaE7?w=294&h=196&c=7&r=0&o=7&dpr=1.3&pid=1.7&rm=3",
    ],
).launch()
