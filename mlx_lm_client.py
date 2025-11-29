import tkinter as tk
from tkinter import scrolledtext, messagebox
from tkinter.font import Font
from tkinter import PanedWindow, Text, Scrollbar, VERTICAL, HORIZONTAL, WORD, BOTH, Y, RIGHT, LEFT, X, YES, simpledialog
import traceback
import requests
import threading
import json
import time
import sys
import argparse
import os
import jinja2
import pyperclip
import tempfile
import matplotlib.pyplot as plt
import re
import webbrowser
import html

def insert_to_readonly(text_window, newtext, highlight=False, autoscroll=True):
    text_window.config(state=tk.NORMAL)
    if highlight:
        insert_highlighted_text(text_window, newtext)
    else:
        text_window.insert(tk.END, newtext)
    text_window.config(state=tk.DISABLED)
    if autoscroll:
        text_window.see(tk.END)
    return


# Create the parser
parser = argparse.ArgumentParser(description="MLX LLM client with tkinter")

# Add positional arguments for the three filenames
parser.add_argument("--config_file", type=str, help="config.json to set chat template")
parser.add_argument("--param_file", type=str, help="param.json to set sampling params")
parser.add_argument("--history_file", default="", type=str, help="history.json to set history chat context")

global_autoscroll = False

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
        insert_to_readonly(text_window, f"\n{user}: ", highlight=True)
        insert_to_readonly(text_window, user_input, highlight=False)
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
    global global_autoscroll

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

        insert_to_readonly(text_window, f"\n{char}: ", highlight=True)

        for chunk in response.iter_lines(decode_unicode=True):
            if chunk.startswith("data: "):  # Handle only JSON lines
                chunk_data = chunk[6:]  # Remove the "data: " prefix
                if "[DONE]" in chunk_data:
                    continue
                try:
                    parsed_data = json.loads(chunk_data)
                    for choice in parsed_data.get("choices", []):
                        text = choice.get("text", "")
                        response_text += text
                        # Update GUI in real-time
                        insert_to_readonly(text_window, text, highlight=False, autoscroll=global_autoscroll)
                        if text_window.yview()[1] == 1.0:
                            # if scrollbar at bottom
                            enable_autoscroll()
                except Exception:
                    traceback.print_exc()
                    exit()
                root.update()

        # Add assistant message to chat history
        global_chat_history["messages"].append({
            "role": "assistant",
            "content": response_text
        })
        # Finalize GUI response with a newline
        insert_to_readonly(text_window, "\n")
        with open(history_filename,"w",encoding="utf8") as f:
            json.dump(global_chat_history, f, indent=2)

    except requests.RequestException as e:
        insert_to_readonly(text_window, f"\nError: {e}\n")

def change_font_size(event):
    widget = event.widget  # Get the widget that triggered the event
    current_font = Font(font=widget.cget("font"))
    new_size = current_font.actual()["size"] + (1 if event.delta > 0 else -1)
    new_size = max(8, new_size)  # Ensure the font size doesn't go below 8
    widget.configure(font=(current_font.actual()["family"], new_size))

def enable_autoscroll():
    global global_autoscroll
    global_autoscroll = True
    return

def disable_autoscroll(event):
    global global_autoscroll
    global_autoscroll = False
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

def show_formula_browser(latex_formula):
    """Open in system browser - guaranteed MathJax support"""
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <script src="https://polyfill.io/v3/polyfill.min.js?features=es6"></script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <script>
    MathJax = {{
        tex: {{
            inlineMath: [['$', '$']],
            displayMath: [['$$', '$$']],
            processEscapes: true
        }},
        svg: {{
            fontCache: 'global'
        }}
    }};
    </script>
    <style>
        body {{ 
            font-family: Arial, sans-serif; 
            margin: 40px;
            background: #f5f5f5;
        }}
        .container {{ 
            background: white; 
            padding: 30px; 
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .formula {{ 
            font-size: 24px;
            margin: 20px 0;
            color: #333;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="formula">{latex_formula}</div>
    </div>
</body>
</html>"""
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False, encoding='utf-8') as f:
        f.write(html_content)
        temp_file = f.name
    
    # Open in default browser
    webbrowser.open(f'file://{temp_file}')
    
    # The file will be deleted when the program exits
    return temp_file

def render_latex_browser(text_widget):
    """Render using system browser"""
    try:
        selected_text = text_widget.get(tk.SEL_FIRST, tk.SEL_LAST)
        #cleaned_text = selected_text.strip()
        ## Remove surrounding delimiters if present
        #cleaned_text = re.sub(r'^\$+|\$+$|^\\[\[\]]|\\[\[\]]$', '', cleaned_text)
        #cleaned_text = cleaned_text.strip()
        show_formula_browser(selected_text)
        
    except Exception as e:
        messagebox.showerror("Error", f"Error rendering LaTeX: {str(e)}")

def show_context_menu(event):
    menu = tk.Menu(root, tearoff=0)
    menu.add_command(label="Cut", command=lambda: cut_text(event.widget))
    menu.add_command(label="Copy", command=lambda: copy_text(event.widget))
    menu.add_command(label="Paste", command=lambda: paste_text(event.widget))
    menu.add_command(label="Delete", command=lambda: delete_text(event.widget))
    menu.add_command(label="Render", command=lambda: render_latex_browser(event.widget))
    
    # Display the menu at the mouse position
    menu.post(event.x_root, event.y_root)

class TextLineNumbers(tk.Canvas):
    def __init__(self, *args, **kwargs):
        tk.Canvas.__init__(self, *args, **kwargs)
        self.textwidget = None
        self.font = tk.font.Font(family="Monospace", size=10)  # Monospace font

    def attach(self, text_widget):
        self.textwidget = text_widget
        
    def redraw(self, *args):
        self.delete("all")
        if not self.textwidget: return
        
        i = self.textwidget.index("@0,0")
        max_line = 0  # Track maximum line number width
        while True:
            dline = self.textwidget.dlineinfo(i)
            if not dline: break
            y = dline[1]
            linenum = str(i).split('.')[0]
            
            # Calculate text width
            text_width = self.font.measure(linenum + " ")
            max_line = max(max_line, text_width)
            
            # Draw text aligned to right edge
            self.create_text(max_line + 5, y, 
                           anchor="ne", text=linenum,
                           font=self.font, fill='blue')
            i = self.textwidget.index("%s+1line" % i)
        
        # Set canvas width to maximum line number width + padding
        self.config(width=max_line + 10)

class CustomText(tk.Text):
    def __init__(self, *args, **kwargs):
        tk.Text.__init__(self, *args, **kwargs)

        # create a proxy for the underlying widget
        self._orig = self._w + "_orig"
        self.tk.call("rename", self._w, self._orig)
        self.tk.createcommand(self._w, self._proxy)

        self.search_query = None
        self.search_pos = "1.0"
        self.search_active = False
        self.search_wrapped = False

    def _proxy(self, *args):
        # let the actual widget perform the requested action
        cmd = (self._orig,) + args
        result = self.tk.call(cmd)

        # generate an event if something was added or deleted,
        # or the cursor position changed
        if (args[0] in ("insert", "replace", "delete") or 
            args[0:3] == ("mark", "set", "insert") or
            args[0:2] == ("xview", "moveto") or
            args[0:2] == ("xview", "scroll") or
            args[0:2] == ("yview", "moveto") or
            args[0:2] == ("yview", "scroll")
        ):
            self.event_generate("<<Change>>", when="tail")

        # return what the actual widget returned
        return result  

def switch_text_areas(event):
    if root.focus_get() == user_text_area:
        text_window.focus_set()
    else:
        user_text_area.focus_set()
    return "break"


def search(event=None, widget=None):
    if widget is None:
        widget = event.widget
    
    # Ask for search query
    query = simpledialog.askstring("Search", "Enter text:", parent=widget)
    if not query:
        return
    
    # Initialize new search
    widget.search_query = query
    widget.search_pos = "1.0"
    widget.search_wrapped = False
    _search_next(widget, new_search=True)

def _search_next(widget=None, new_search=False, event=None):
    if widget is None or widget.search_active or not widget.search_query:
        return
    
    widget.search_active = True
    try:
        widget.tag_remove('found', '1.0', tk.END)
        widget.tag_remove('current_match', '1.0', tk.END)

        if new_search:
            start_pos = "1.0"
        else:
            start_pos = widget.search_pos

        pos_start = widget.search(widget.search_query, start_pos,
                                stopindex=tk.END, nocase=True)
        
        if pos_start:
            # Found match
            pos_end = f"{pos_start}+{len(widget.search_query)}c"
            widget.tag_add("found", pos_start, pos_end)
            widget.tag_add("current_match", pos_start, pos_end)
            widget.see(pos_start)
            widget.search_pos = pos_end
            widget.search_wrapped = False
        else:
            # No matches - wrap around if not already wrapped
            if not widget.search_wrapped:
                widget.search_wrapped = True
                widget.search_pos = "1.0"
                _search_next(widget, new_search=True)
            else:
                messagebox.showinfo("Search", "No more matches")
                widget.search_pos = "1.0"
                widget.search_wrapped = False

        widget.tag_config('current_match', background='orange')
        widget.tag_config('found', background='yellow')
    finally:
        widget.search_active = False

# Create main Tkinter window
root = tk.Tk()
root.grid_columnconfigure(0, weight=1)
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
chat_frame.grid_rowconfigure(0, weight=1)
chat_frame.grid_columnconfigure(1, weight=1)
linenumbers_chat = TextLineNumbers(chat_frame, width=10)
linenumbers_chat.grid(row=0, column=0, sticky="ns")

text_window = CustomText(chat_frame, wrap=WORD, state=tk.DISABLED)
text_window.tag_configure("highlight", foreground="red", font=tk.font.Font(weight="bold"))
text_scroll = Scrollbar(chat_frame, orient=VERTICAL, command=text_window.yview, takefocus=0)
text_window.config(yscrollcommand=text_scroll.set)

text_window.bind("<MouseWheel>", disable_autoscroll)
text_window.bind("<Control-MouseWheel>", change_font_size)
text_window.bind("<Up>", disable_autoscroll)

text_window_on_change = lambda event: linenumbers_chat.redraw()
text_window.bind("<<Change>>", text_window_on_change)
text_window.bind("<<Configure>>", text_window_on_change)
linenumbers_chat.attach(text_window)

text_window.grid(row=0, column=1, sticky="nsew")
if "messages" in global_chat_history:
    for chat in global_chat_history["messages"]:
        role, content = chat["role"], chat["content"]
        insert_to_readonly(text_window, f"\n{role}: ", highlight=True)
        insert_to_readonly(text_window, content)

# Add right-click bindings to both text windows
if sys.platform == "darwin":  # macOS
    text_window.bind("<Button-2>", show_context_menu)
else:  # Windows/Linux
    text_window.bind("<Button-3>", show_context_menu)

text_scroll.bind("<ButtonPress>", disable_autoscroll)

# Pack the Text widget and Scrollbar
text_scroll.grid(row=0, column=2, sticky="ns")

# Add the chat frame to the PanedWindow
paned_window.add(chat_frame)

# User input section (bottom pane)
input_frame = tk.Frame(paned_window)
user_text_area = Text(input_frame, wrap=WORD)
user_text_scroll = Scrollbar(input_frame, orient=VERTICAL, command=user_text_area.yview, takefocus=0)
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

text_window.bind("<Control-Shift-Tab>", switch_text_areas)
user_text_area.bind("<Control-Shift-Tab>", switch_text_areas)
# Update bindings to use widget parameter directly
text_window.bind("<Control-g>", lambda e: _search_next(widget=text_window))
text_window.bind("<Control-f>", lambda e: search(widget=text_window))

def on_closing():
    print("Window is closing...")
    root.after(2, root.destroy)  # Close the window
    sys.exit()

root.protocol("WM_DELETE_WINDOW", on_closing)

root.mainloop()
