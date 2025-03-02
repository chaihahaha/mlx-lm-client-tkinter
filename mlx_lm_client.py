import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkinter.font import Font
from tkinter import PanedWindow, Text, Scrollbar, VERTICAL, HORIZONTAL, WORD, BOTH, Y, RIGHT, LEFT, X, YES

import requests
import threading
import json
import time
import configparser
import sys
import yaml
import argparse
import os

class FileInterpolation(configparser.BasicInterpolation):
    def before_get(self, parser, section, option, value, defaults):
        # Check for custom file inclusion syntax
        if value.startswith("%(file:") and value.endswith(")f"):
            file_path = value[7:-2]  # Extract the file path
            if os.path.exists(file_path):
                with open(file_path, 'r') as file:
                    return file.read().strip()
        
        # Fall back to the default interpolation behavior
        return super().before_get(parser, section, option, value, defaults)


# Create the parser
parser = argparse.ArgumentParser(description="MLX LLM client with tkinter")

# Add positional arguments for the two filenames
parser.add_argument("--config_file", type=str, help="config.ini to set chat template")
parser.add_argument("--param_file", type=str, help="param.yaml to set sampling params")

# Parse the arguments
args = parser.parse_args()

# Load configuration from file
config = configparser.ConfigParser(interpolation=FileInterpolation())
config.read(args.config_file)
instruct_config = dict(config["INSTRUCT"])
server_config = dict(config["SERVER"])

instruct_settings = ["system_prefix", "system_suffix", "input_prefix", "input_suffix", "output_prefix", "output_suffix", "char", "user", "system_sequence", "stop_sequence", "last_output_prefix"]
server_settings = ["global_chat_history", "server_address"]

# Assert instruct config fields
for key in instruct_settings:
    assert key in instruct_config

# Assert server config fields
for key in server_settings:
    assert key in server_config

for key in instruct_settings:
    should_be_token = instruct_config[key]
    #if should_be_token and not should_be_token.endswith(" "):
    #    instruct_config[key] = should_be_token+" "

# Update locals() with the config dictionary
locals().update(instruct_config)
locals().update(server_config)
autoscroll = False

params = dict()
with open(args.param_file,'r') as f:
    params.update(yaml.safe_load(f))

param_names = ["add_bos_token", "do_sample", "dynatemp_base", "early_stopping", "epsilon_cutoff", "eta_cutoff", "grammar", "guidance_scale", "length_penalty", "max_context_length", "max_tokens", "min_length", "min_p", "mirostat", "mirostat_eta", "mirostat_tau", "negative_prompt", "no_repeat_ngram_size", "num_beams", "penalty_alpha", "repetition_penalty", "repetition_penalty_range", "seed", "skip_special_tokens", "smoothing_factor", "stream", "temperature", "tfs", "top_a", "top_k", "top_p", "typical_p", "use_default_badwordids"]
for key in param_names:
    assert key in params.keys()

# Function to send the message and display it in the GUI
def send_message(user_text_area):
    user_input = user_text_area.get("1.0", tk.END).strip()  # Get user input
    if user_input.strip():  # Ensure the input is not empty
        text_window.config(state=tk.NORMAL)
        text_window.insert(tk.END, f"\nUser: {user_input}")
        text_window.config(state=tk.DISABLED)
        text_window.see(tk.END)
        #user_text_area.delete(0, tk.END)  # Clear the entry widget
        user_text_area.delete("1.0", tk.END)  # Clear the text area
        
        threading.Thread(target=send_request, args=(user_input,)).start()  # Call the function to send the request

history_filename = f'history-{time.time()}.txt'

def send_request(user_input):
    global global_chat_history
    global autoscroll
    if not global_chat_history:
        global_chat_history += f"{system_prefix} {system_sequence} {system_suffix} {output_prefix} {output_suffix} {input_prefix} {user_input} {input_suffix} {last_output_prefix}\n"
    else:
        global_chat_history += f"{input_prefix} {user_input} {input_suffix} {last_output_prefix}\n"
    payload = {
        "prompt": global_chat_history,
        "stop": [stop_sequence],
    }
    payload.update(params)

    try:
        response = requests.post(server_address, json=payload, stream=True)
        response.raise_for_status()
        response_text = ""

        text_window.config(state=tk.NORMAL)
        text_window.insert(tk.END, f"\n{char}: ")
        text_window.config(state=tk.DISABLED)
        text_window.see(tk.END)

        for chunk in response.iter_lines(decode_unicode=True):
            if chunk.startswith("data: "):  # Handle only JSON lines
                chunk_data = chunk[6:]  # Remove the "data: " prefix
                try:
                    parsed_data = json.loads(chunk_data)
                    for choice in parsed_data.get("choices", []):
                        text = choice.get("text", "")
                        response_text += text
                        # Update GUI in real-time
                        text_window.config(state=tk.NORMAL)
                        text_window.insert(tk.END, text)
                        text_window.config(state=tk.DISABLED)
                        if text_window.yview()[1] == 1.0:
                            # if scrollbar at bottom
                            enable_autoscroll()
                        if autoscroll:
                            text_window.see(tk.END)
                except json.JSONDecodeError:
                    # Handle potential malformed JSON
                    pass
                root.update()

        global_chat_history += f"{response_text}{stop_sequence}"
        # Finalize GUI response with a newline
        text_window.config(state=tk.NORMAL)
        text_window.insert(tk.END, "\n")
        text_window.config(state=tk.DISABLED)
        with open(history_filename,"w",encoding="utf8") as f:
            f.write(global_chat_history)

    except requests.RequestException as e:
        text_window.config(state=tk.NORMAL)
        text_window.insert(tk.END, f"Error: {e}\n")
        text_window.config(state=tk.DISABLED)

def change_font_size(event):
    widget = event.widget  # Get the widget that triggered the event
    current_font = Font(font=widget.cget("font"))
    new_size = current_font.actual()["size"] + (1 if event.delta > 0 else -1)
    new_size = max(8, new_size)  # Ensure the font size doesn't go below 8
    widget.configure(font=(current_font.actual()["family"], new_size))

def enable_autoscroll():
    global autoscroll
    autoscroll = True
    return

def disable_autoscroll(event):
    global autoscroll
    autoscroll = False
    return

# Create main Tkinter window
root = tk.Tk()
root.title("Chat with MLX LLM")
root.geometry("800x600")  # Set an initial window size

# Configure grid layout
root.grid_rowconfigure(0, weight=1)  # Row 0 paned window
root.grid_rowconfigure(1, weight=0)  # Row 1 button fixed
root.grid_columnconfigure(0, weight=1)  # Widgets expand horizontally


# Create a PanedWindow for a draggable separator
paned_window = PanedWindow(root, orient=tk.VERTICAL)
paned_window.grid(row=0, column=0, sticky="nsew")  # Row 0, Column 0

# Chat history section (top pane)
chat_frame = tk.Frame(paned_window)
text_window = Text(chat_frame, wrap=WORD)
text_scroll = Scrollbar(chat_frame, orient=VERTICAL, command=text_window.yview)
text_window.config(yscrollcommand=text_scroll.set)

text_window.bind("<MouseWheel>", disable_autoscroll)
text_window.bind("<Control-MouseWheel>", change_font_size)

# Pack the Text widget and Scrollbar
text_window.pack(side=LEFT, fill=BOTH, expand=1)
text_scroll.pack(side=RIGHT, fill=Y)

# Add the chat frame to the PanedWindow
paned_window.add(chat_frame)

# User input section (bottom pane)
input_frame = tk.Frame(paned_window)
user_text_area = Text(input_frame, wrap=WORD)
user_text_scroll = Scrollbar(input_frame, orient=VERTICAL, command=user_text_area.yview)
user_text_scroll.bind("<ButtonPress>", disable_autoscroll)
user_text_area.config(yscrollcommand=user_text_scroll.set)

# Pack the Text widget and Scrollbar
user_text_area.pack(side=LEFT, fill=BOTH, expand=1)
user_text_scroll.pack(side=RIGHT, fill=Y)

user_text_area.bind("<Shift-Return>", lambda event: send_message(user_text_area))
# Bind mouse wheel event to change font size
user_text_area.bind("<Control-MouseWheel>", change_font_size)
user_text_area.pack(expand=True, fill='both')

# Add the input frame to the PanedWindow
paned_window.add(input_frame)

# Allow the separator to be draggable
paned_window.paneconfigure(chat_frame, stretch="always")
paned_window.paneconfigure(input_frame, stretch="always")

button_container = tk.Frame(root)
button_container.grid(row=1, column=0, padx=10, pady=5, sticky="ew")
# Create send button
send_button = tk.Button(button_container, text="Send", command=lambda: send_message(user_text_area))
send_button.pack(side=RIGHT, fill=X)  # Fill the container horizontally

root.mainloop()
