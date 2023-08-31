from transformers import CLIPTextModel, CLIPTokenizer

CLIPTokenizer.from_pretrained("openai/clip-vit-large-patch14")

# Largest one
CLIPTextModel.from_pretrained("openai/clip-vit-large-patch14")
