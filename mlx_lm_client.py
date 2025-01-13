import tkinter as tk
from tkinter import scrolledtext, messagebox
import requests
import threading
import json

# Function to send the message and display it in the GUI
def send_message(user_text_area):
    user_input = user_text_area.get("1.0", tk.END).strip()  # Get user input
    if user_input.strip():  # Ensure the input is not empty
        text_window.config(state=tk.NORMAL)
        text_window.insert(tk.END, f"User: {user_input}")
        text_window.config(state=tk.DISABLED)
        text_window.see(tk.END)
        #user_text_area.delete(0, tk.END)  # Clear the entry widget
        user_text_area.delete("1.0", tk.END)  # Clear the text area
        
        send_request(user_input)  # Call the function to send the request

system_prefix = "<|start_header_id|>Instruction: <|end_header_id|>\n\n"
output_prefix = "<|start_header_id|>Response: <|end_header_id|>\n\n"
char = "Assistant"
user = "User"
system_sequence = f"Write the next replay in a chat between {char} and {user}"
eot = "<|eot_id|>"
input_prefix = "<|start_header_id|>Input: <|end_header_id|>\n\n"
last_output_prefix = "<|start_header_id|>{char}: <|end_header_id|>\n\n"
global_chat_history = ""

def send_request(user_input):
    global global_chat_history
    if not global_chat_history:
        prompt_text = f"{system_prefix}{system_sequence}{eot}{output_prefix}{eot}{input_prefix}{user_input}{eot}{last_output_prefix}"
    else:
        global_chat_history += f"{input_prefix}{user_input}{eot}{last_output_prefix}"
        prompt_text = global_chat_history
    payload = {
        "max_context_length": 32769,
        "max_tokens": 752,
        "stream": True,
        "repetition_penalty": 1.08,
        "repetition_penalty_range": 14,
        "temperature": 0.8,
        "tfs": 1,
        "top_a": 0.04,
        "top_p": 0.9,
        "top_k": 43,
        "typical_p": 1,
        "min_p": 0,
        "smoothing_factor": 0,
        "seed": -1,
        "dynatemp_base": 1,
        "mirostat": 0,
        "mirostat_tau": 4.99,
        "mirostat_eta": 0,
        "epsilon_cutoff": 0,
        "eta_cutoff": 0,
        "min_length": 37,
        "no_repeat_ngram_size": 0,
        "guidance_scale": 0.01,
        "use_default_badwordids": False,
        "add_bos_token": True,
        "skip_special_tokens": False,
        "do_sample": False,
        "grammar": "",
        "negative_prompt": "",
        "num_beams": 2,
        "penalty_alpha": 0,
        "length_penalty": 0,
        "early_stopping": False,
        "prompt": prompt_text,
        "stop_sequence": [eot],
    }

    try:
        response = requests.post("http://192.168.8.228:8080/v1/completions", json=payload, stream=True)
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
                        text_window.see(tk.END)
                except json.JSONDecodeError:
                    # Handle potential malformed JSON
                    pass
                root.update()

        global_chat_history += f"{response_text}{eot}"
        # Finalize GUI response with a newline
        text_window.config(state=tk.NORMAL)
        text_window.insert(tk.END, "\n")
        text_window.config(state=tk.DISABLED)

    except requests.RequestException as e:
        text_window.config(state=tk.NORMAL)
        text_window.insert(tk.END, f"Error: {e}\n")
        text_window.config(state=tk.DISABLED)


# Create main Tkinter window
root = tk.Tk()
root.title("Chat with LLM")
root.geometry("800x600")  # Set an initial window size

# Configure grid layout
root.grid_rowconfigure(0, weight=1)  # Chat history expands vertically
root.grid_rowconfigure(1, weight=1)  # User input expands vertically
root.grid_columnconfigure(0, weight=1)  # Widgets expand horizontally

# Create chat history display
text_window = scrolledtext.ScrolledText(root, wrap=tk.WORD, state=tk.DISABLED)
text_window.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

# Create user input area
user_text_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, height=5)
user_text_area.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")


# Create send button
send_button = tk.Button(root, text="Send", command=lambda: send_message(user_text_area))
send_button.grid(row=2, column=1, padx=10, pady=5, sticky="e")
root.mainloop()

