import gradio as gr
from modules import scripts
import requests
import shutil
from PIL import Image  # Import the Pillow library
from tagger import ui  # pylint: disable=import-error
from tagger import utils  # pylint: disable=import-error
from tagger import interrogator  # pylint: disable=import-error

# Function to refresh interrogator names
def refresh_interrogator_names():
    utils.refresh_interrogators()
    interrogator_names = sorted(x.name for x in utils.interrogators.values())
    interrogator_names.append("Run Both")  # Add the "Run Both" option
    return interrogator_names

# Function to run interrogator (placeholder, replace with actual logic)
def run_interrogator(model_name, pil_image):
    interrogator_instance = interrogator.Interrogator(model_name)
    prompt_tags = interrogator_instance.interrogate(image_path)
    prompt_tags = ui.on_interrogate_image_submit(
            image=pil_image,  # The PIL Image object
            name=model_name,  # The name of the interrogator (model) selected from the dropdown
            filt=None  # Filter string, if applicable
        )
    return prompt_tags

# Function to combine prompts
def combine_prompts(tag_lists):
    combined_tokens = []
    for tag_list in tag_lists:
        tokens = tag_list.split(',')
        combined_tokens.extend(tokens)
    token_count = {}
    for token in combined_tokens:
        token = token.strip()
        token_count[token] = token_count.get(token, 0) + 1
    final_prompt = []
    for token, count in token_count.items():
        if count == 1:
            final_prompt.append(f"{token}")
        else:
            weight = min(1.25 + (count - 2) * 0.25, 2)
            final_prompt.append(f"{token}:{weight}")
    return ','.join(final_prompt)

# Fetch tags function
def fetchTags(ch, art_box, char_box, selected_model, image_component):
    try:
        if "danbooru.donmai.us/posts" not in ch:
            return "unsupported url"

        url = ch + ".json"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.3'}
        with requests.get(url, headers=headers) as r:
            data = r.json()
            artist = data["tag_string_artist"]
            char = data["tag_string_character"]
            general_tags = data["tag_string_general"]
            image_url = data["file_url"]

        # Download the image
        image_response = requests.get(image_url, stream=True, headers=headers)
        image_response.raise_for_status()
        with open('downloaded_image.jpg', 'wb') as f:
            shutil.copyfileobj(image_response.raw, f)

        # Create a PIL Image object from the downloaded image
        pil_image = Image.open('downloaded_image.jpg')

        # Update the Gradio Image component with the PIL Image object
        image_component.update(pil_image)
        
        # Replace underscores with spaces in tags
        artist = artist.replace("_", " ")
        char = char.replace("_", " ")
        general_tags = general_tags.replace("_", " ")

        # Determine which models to run
        if selected_model == "Run Both":
            selected_models = ["ML-Danbooru Caformer dec-5-97527", "WD14 moat tagger v2"]  # Replace with the actual model names
        else:
            selected_models = [selected_model]

        # Run the selected models
        all_prompts = []
        for model in selected_models:
            interrogation_tags = run_interrogator(model, pil_image)
            all_prompts.append(interrogation_tags)

        # Combine all interrogation tags and danbooru tags
        combined_tags = f"{artist} {char} {general_tags}"
        all_prompts.append(combined_tags.replace(" ", ", "))

        # Combine Danbooru and interrogation tags
        combined_tags = combine_prompts(all_prompts)

        return combined_tags

    except Exception as err:
        return f"Error: {err}"

# Gradio UI
class BooruScript(scripts.Script):
    def __init__(self) -> None:
        super().__init__()

    def title(self):
        return ("Link fetcher")

    def show(self):
        return scripts.AlwaysVisible

    def ui(self, is_img2img):
        with gr.Group():
            with gr.Accordion("DanBooru Link", open=False):
                fetch_tags = gr.Button(value='Get Tags', variant='primary')
                link = gr.Textbox(label="insert link")

                with gr.Row():
                    # Add an Image component to display the fetched image
                    image_component = gr.Image(
                        label='Fetched Image',
                        source='upload',
                        interactive=True,
                        type="pil"
                    )

                with gr.Row():
                    includeartist = gr.Checkbox(value=True, label="Include artist tags", interactive=True)
                    includecharacter = gr.Checkbox(value=True, label="Include character tags", interactive=True)

                with gr.Row(variant='compact'):
                    # Model selector dropdown
                    interrogator_names = refresh_interrogator_names()
                    model_selector = gr.Dropdown(
                        label='Model',
                        choices=interrogator_names,
                        value=(None if len(interrogator_names) < 1 else interrogator_names[-1])
                    )

                    # Refresh button
                    refresh_button = gr.Button(value='Refresh')
                    refresh_button.click(fn=lambda: {'choices': refresh_interrogator_names()}, outputs=[model_selector])

                    # Unload all models button
                    unload_button = gr.Button(value='Unload all models')
                    unload_button.click(fn=ui.unload_interrogators)  # Using the unload_interrogators function here

        # Link the fetchTags function to the Image component
        if is_img2img:
            fetch_tags.click(
                fn=fetchTags,
                inputs=[link, includeartist, includecharacter, model_selector, image_component],
                outputs=[self.boxxIMG]
            )
        else:
            fetch_tags.click(
                fn=fetchTags,
                inputs=[link, includeartist, includecharacter, model_selector, image_component],
                outputs=[self.boxx]
            )

        return [link, fetch_tags, image_component, includeartist, includecharacter, model_selector, refresh_button, unload_button]

    def after_component(self, component, **kwargs):
        if kwargs.get("elem_id") == "txt2img_prompt":
            self.boxx = component
        if kwargs.get("elem_id") == "img2img_prompt":
            self.boxxIMG = component
