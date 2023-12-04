#This is an example that uses the websockets api to know when a prompt execution is done
#Once the prompt execution is done it downloads the images using the /history endpoint
import asyncio
import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import urllib.request
import urllib.parse
import sys  # Import the sys module to access command line arguments
from telegram import Bot, InputMediaPhoto
from PIL import Image
from io import BytesIO

# Check if the prompt_param is provided as a command line argument
if len(sys.argv) < 2:
    print("Please provide a prompt_param as a command line argument.")
    sys.exit(1)

prompt_param = sys.argv[1]  # Get the prompt_param from command line argument

if len(sys.argv) < 3:
  negativePrompt_param = ""
else:
  negativePrompt_param = sys.argv[2]  # Get the negativePrompt_param from command line argument

if len(sys.argv) < 4:
  noise_seed_param = 0
else:
  noise_seed_param = sys.argv[3]  # Get the noise_seed_param from command line argument

# Replace with your actual bot token 
bot_token = '9999999999:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA'
# Replace 'YOUR_CHAT_ID' with the actual chat ID where you want to send the image
chat_id = 'YOUR_CHAT_ID'

#address to comfyui
server_address = "127.0.0.1:8188"
client_id = str(uuid.uuid4())

def queue_prompt(prompt):
    p = {"prompt": prompt, "client_id": client_id}
    data = json.dumps(p).encode('utf-8')
    req =  urllib.request.Request("http://{}/prompt".format(server_address), data=data)
    return json.loads(urllib.request.urlopen(req).read())

def get_image(filename, subfolder, folder_type):
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    with urllib.request.urlopen("http://{}/view?{}".format(server_address, url_values)) as response:
        return response.read()

def get_history(prompt_id):
    with urllib.request.urlopen("http://{}/history/{}".format(server_address, prompt_id)) as response:
        return json.loads(response.read())

def get_images(ws, prompt):
    prompt_id = queue_prompt(prompt)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break #Execution is done
        else:
            continue #previews are binary data

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output

    return output_images

prompt_text = """
{
  "5": {
    "inputs": {
      "width": 768,
      "height": 512,
      "batch_size": 4
    },
    "class_type": "EmptyLatentImage"
  },
  "6": {
    "inputs": {
      "text": "",
      "clip": [
        "20",
        1
      ]
    },
    "class_type": "CLIPTextEncode"
  },
  "7": {
    "inputs": {
      "text": "text, watermark",
      "clip": [
        "20",
        1
      ]
    },
    "class_type": "CLIPTextEncode"
  },
  "8": {
    "inputs": {
      "samples": [
        "13",
        0
      ],
      "vae": [
        "20",
        2
      ]
    },
    "class_type": "VAEDecode"
  },
  "13": {
    "inputs": {
      "add_noise": true,
      "noise_seed": 0,
      "cfg": 1,
      "model": [
        "20",
        0
      ],
      "positive": [
        "6",
        0
      ],
      "negative": [
        "7",
        0
      ],
      "sampler": [
        "14",
        0
      ],
      "sigmas": [
        "22",
        0
      ],
      "latent_image": [
        "5",
        0
      ]
    },
    "class_type": "SamplerCustom"
  },
  "14": {
    "inputs": {
      "sampler_name": "euler_ancestral"
    },
    "class_type": "KSamplerSelect"
  },
  "20": {
    "inputs": {
      "ckpt_name": "sd_xl_turbo_1.0_fp16.safetensors"
    },
    "class_type": "CheckpointLoaderSimple"
  },
  "22": {
    "inputs": {
      "steps": 1,
      "model": [
        "20",
        0
      ]
    },
    "class_type": "SDTurboScheduler"
  },
  "25": {
    "inputs": {
      "images": [
        "8",
        0
      ]
    },
    "class_type": "PreviewImage"
  }
}
"""

prompt = json.loads(prompt_text)
#set the text prompt for our positive CLIPTextEncode
prompt["6"]["inputs"]["text"] = prompt_param
prompt["7"]["inputs"]["text"] = negativePrompt_param
prompt["13"]["inputs"]["noise_seed"] = noise_seed_param

#set the seed for our KSampler node
#prompt["3"]["inputs"]["seed"] = 5

ws = websocket.WebSocket()
ws.connect("ws://{}/ws?clientId={}".format(server_address, client_id))
images = get_images(ws, prompt)

#Commented out code to display the output images:

#for node_id in images:
#    for image_data in images[node_id]:
#        from PIL import Image
#        import io
#        image = Image.open(io.BytesIO(image_data))
#        image.show()

# Initialize your Telegram bot with your bot token
bot = Bot(token=bot_token)

# Create a list to hold the media items
media_items = []

# Process each image data and convert it into a format that Telegram expects
for node_id in images:
    for image_data in images[node_id]:
        image = Image.open(BytesIO(image_data))
        # Save the image into a BytesIO object
        img_buffer = BytesIO()
        image.save(img_buffer, format='PNG')  # Change format as needed
        img_buffer.seek(0)
        media_items.append(InputMediaPhoto(media=img_buffer, caption="Prompt: {} *** Negative Prompt: {} *** noise_seed: {}".format(prompt_param, negativePrompt_param, noise_seed_param)))

async def send_images():
    # Send the images as a media group
    await bot.send_media_group(chat_id=chat_id, media=media_items)

# Run the async function within an event loop
import asyncio
loop = asyncio.get_event_loop()
loop.run_until_complete(send_images())