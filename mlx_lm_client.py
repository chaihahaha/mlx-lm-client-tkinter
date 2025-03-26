import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkinter.font import Font
from tkinter import PanedWindow, Text, Scrollbar, VERTICAL, HORIZONTAL, WORD, BOTH, Y, RIGHT, LEFT, X, YES

import requests
import threading
import json
import time
import sys
import argparse
import os
import jinja2
import pyperclip

# Create the parser
parser = argparse.ArgumentParser(description="MLX LLM client with tkinter")

# Add positional arguments for the three filenames
parser.add_argument("--config_file", type=str, help="config.json to set chat template")
parser.add_argument("--param_file", type=str, help="param.json to set sampling params")
parser.add_argument("--history_file", default="", type=str, help="history.json to set history chat context")

autoscroll = False

# Parse the arguments
args = parser.parse_args()

# Load configuration file
with open(args.config_file, "r", encoding="utf8") as f:
    config = json.load(f)

settings = ["char", "user", "system_sequence", "stop_sequence", "last_output_prefix", "chat_template", "server_address"]

# Assert config fields
for key in settings:
    assert key in config

# Update locals() with the config dictionary
locals().update(config)
jinja2_chat_template = jinja2.Template(chat_template)

# Load parameter file
with open(args.param_file, "r", encoding="utf8") as f:
    params = json.load(f)

param_names = ["add_bos_token", "do_sample", "dynatemp_base", "early_stopping", "epsilon_cutoff", "eta_cutoff", "grammar", "guidance_scale", "length_penalty", "max_context_length", "max_tokens", "min_length", "min_p", "mirostat", "mirostat_eta", "mirostat_tau", "negative_prompt", "no_repeat_ngram_size", "num_beams", "penalty_alpha", "repetition_penalty", "repetition_penalty_range", "seed", "skip_special_tokens", "smoothing_factor", "stream", "temperature", "tfs", "top_a", "top_k", "top_p", "typical_p", "use_default_badwordids"]
for key in param_names:
    assert key in params.keys()

# Load history file
if not os.path.isfile(args.history_file):
    global_chat_history = []
else:
    with open(args.history_file, "r") as f:
        global_chat_history = json.load(f)
history_filename = f'history-{time.time()}.txt'

# Function to send the message and display it in the GUI
def send_message(user_text_area):
    user_input = user_text_area.get("1.0", tk.END).strip()  # Get user input
    if user_input.strip():  # Ensure the input is not empty
        text_window.config(state=tk.NORMAL)
        insert_highlighted_text(text_window, f"\n{user}: ")
        text_window.insert(tk.END, user_input)
        text_window.config(state=tk.DISABLED)
        text_window.see(tk.END)
        #user_text_area.delete(0, tk.END)  # Clear the entry widget
        user_text_area.delete("1.0", tk.END)  # Clear the text area
        
        threading.Thread(target=send_request, args=(user_input,)).start()  # Call the function to send the request

def insert_highlighted_text(text_widget, new_text):
    text_widget.mark_set(tk.INSERT, tk.END)
    insert_index = text_widget.index(tk.INSERT)
    text_widget.insert(insert_index, new_text)
    start_index = insert_index
    end_index = text_widget.index(f"{insert_index} + {len(new_text)}c")
    text_widget.tag_add("highlight", start_index, end_index)
    text_widget.see(tk.END)

def send_request(user_input):
    global global_chat_history
    global autoscroll

    # Initialize chat history if it's empty
    if not global_chat_history:
        global_chat_history = {
            "messages": [
                {"role": "system", "content": f"{system_sequence}"}
            ]
        }
    
    # Add user message
    global_chat_history["messages"].append({
        "role": "user",
        "content": user_input
    })

    payload = {
        "prompt": jinja2_chat_template.render(global_chat_history) + last_output_prefix,
        "stop": [stop_sequence],
    }
    payload.update(params)

    try:
        response = requests.post(server_address, json=payload, stream=True)
        response.raise_for_status()
        response_text = ""

        text_window.config(state=tk.NORMAL)
        insert_highlighted_text(text_window, f"\n{char}: ")
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

        # Add assistant message to chat history
        global_chat_history["messages"].append({
            "role": "assistant",
            "content": response_text
        })
        # Finalize GUI response with a newline
        text_window.config(state=tk.NORMAL)
        text_window.insert(tk.END, "\n")
        text_window.config(state=tk.DISABLED)
        with open(history_filename,"w",encoding="utf8") as f:
            json.dump(global_chat_history, f, indent=2)

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

def copy_text(text_widget):
    text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
    pyperclip.copy(text)

def cut_text(text_widget):
    text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
    pyperclip.copy(text)
    text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)

def paste_text(text_widget):
    text = pyperclip.paste()
    text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)
    text_widget.insert(tk.INSERT, text)

def delete_text(text_widget):
    text_widget.delete(tk.SEL_FIRST, tk.SEL_LAST)

def show_context_menu(event):
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Cut", command=lambda: cut_text(event.widget))
    menu.add_command(label="Copy", command=lambda: copy_text(event.widget))
    menu.add_command(label="Paste", command=lambda: paste_text(event.widget))
    menu.add_command(label="Delete", command=lambda: delete_text(event.widget))
    
    # Display the menu at the mouse position
    menu.post(event.x_root, event.y_root)

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
text_window.tag_configure("highlight", foreground="red", font=tk.font.Font(weight="bold"))
text_window.bind("<Key>", lambda e: None)  # Block all keypresses
text_scroll = Scrollbar(chat_frame, orient=VERTICAL, command=text_window.yview)
text_window.config(yscrollcommand=text_scroll.set)

text_window.bind("<MouseWheel>", disable_autoscroll)
text_window.bind("<Control-MouseWheel>", change_font_size)
text_window.bind("<Up>", disable_autoscroll)
if "messages" in global_chat_history:
    for chat in global_chat_history["messages"]:
        role, content = chat["role"], chat["content"]
        insert_highlighted_text(text_window, f"\n{role}: ")
        text_window.insert(tk.END, content)
        text_window.see(tk.END)

# Add right-click bindings to both text windows
if sys.platform == "darwin":  # macOS
    text_window.bind("<Button-2>", show_context_menu)
else:  # Windows/Linux
    text_window.bind("<Button-3>", show_context_menu)

text_scroll.bind("<ButtonPress>", disable_autoscroll)

# Pack the Text widget and Scrollbar
text_window.pack(side=LEFT, fill=BOTH, expand=1)
text_scroll.pack(side=RIGHT, fill=Y)

# Add the chat frame to the PanedWindow
paned_window.add(chat_frame)

# User input section (bottom pane)
input_frame = tk.Frame(paned_window)
user_text_area = Text(input_frame, wrap=WORD)
user_text_scroll = Scrollbar(input_frame, orient=VERTICAL, command=user_text_area.yview)
user_text_area.config(yscrollcommand=user_text_scroll.set)

# Pack the Text widget and Scrollbar
user_text_area.pack(side=LEFT, fill=BOTH, expand=1)
user_text_scroll.pack(side=RIGHT, fill=Y)

user_text_area.bind("<Shift-Return>", lambda event: send_message(user_text_area))
# Bind mouse wheel event to change font size
user_text_area.bind("<Control-MouseWheel>", change_font_size)
if sys.platform == "darwin":  # macOS
    user_text_area.bind("<Button-2>", show_context_menu)
else:  # Windows/Linux
    user_text_area.bind("<Button-3>", show_context_menu)
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

def on_closing():
    print("Window is closing...")
    root.after(2, root.destroy)  # Close the window
    sys.exit()

root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()
