import ollama
from guidance import gen, models, system, user, assistant
from pynput import keyboard
import threading
from PIL import ImageGrab
import Xlib
import Xlib.display
import time
import subprocess
import re
import os

current_window = None
keystrokes = []

def on_press(key):
    global current_window, keystrokes
    try:
        keystrokes.append((current_window, key.char))
    except AttributeError:
        keystrokes.append((current_window, str(key)))

def get_active_window():
    display = Xlib.display.Display()
    root = display.screen().root
    window_id = root.get_full_property(display.intern_atom('_NET_ACTIVE_WINDOW'), Xlib.X.AnyPropertyType).value[0]
    pid, title = get_active_window_details() or (None, None)
    window_name = re.sub(r'[<>:"/\\|?*]', '_', title)
    process_path = get_process_path(pid) or ""
    try:
        return window_name, window_id, process_path
    except Exception as e:
        print(f"Error in getting window details: {e}")
        return None, None, None

def get_active_window_details():
    try:
        output = subprocess.check_output(["wmctrl", "-lp"]).decode("utf-8")
        active_window_id = subprocess.check_output(["xdotool", "getactivewindow"]).decode("utf-8").strip()
        # Convert the decimal ID to hexadecimal and format it to match wmctrl output
        active_window_id_hex = "0x" + format(int(active_window_id), 'x').zfill(8)
        for line in output.splitlines():
            if active_window_id_hex in line.split()[0]:
                pid = line.split()[2]
                title = line.split(None, 4)[-1]
                return pid, title
        return None, None  # Return None values if active window not found
    except Exception as e:
        print(f"Error: {e}")
        return None, None

def get_process_path(pid):
    try:
        return os.readlink(f"/proc/{pid}/exe")
    except Exception as e:
        print(f"Error in getting process path: {e}")
        return None

def get_window_rect(window_id):
    display = Xlib.display.Display()
    window = display.create_resource_object('window', window_id)
    geom = window.get_geometry()
    return (geom.x, geom.y, geom.x + geom.width, geom.y + geom.height)

def capture_screenshot(window_id, filename):
    rect = get_window_rect(window_id)
    screenshot = ImageGrab.grab(bbox=rect)  # x, y, w, h
    screenshot.save(filename)

def window_monitor():
    global current_window
    last_seen = (None, None)
    while True:
        active_window_name, window_id, process_path = get_active_window()
        if active_window_name != last_seen:
            current_window = active_window_name
            print(f"Capturing window: {active_window_name}")
            print(f"Process path: {process_path}")
            imageFilename = f"images/{active_window_name}_{int(time.time())}.png"
            capture_screenshot(window_id, imageFilename)
            print(f"Captured window: {active_window_name}")
            details = getImageDetails(process_path, imageFilename, active_window_name)
            print(details)
            last_seen = active_window_name
        time.sleep(1)

def keystroke_monitor():
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()

def getImageDetails(process_path, imageFilename, active_window_name):
    print(f"Getting details for {imageFilename} with process path {process_path} and window name {active_window_name}")
    response = ollama.chat(model='llava:34b', messages=[
        {
            'role': 'system',
            'content': f"""You respond only with information you can see in the image, or information you can infer from the image. 
            You may only respond in JSON format. 
            Leave your image observations in the "observations" field array. 
            The "process_path" field should contain the process path. 
            The "application_name" field should contain the Actual Application Name, not the window title. 
            The "application_category" field should contain the category of the application. 
            """
        },
        {
            'role': 'user',
            'content': f"""What is this application? Here may be some important details:
             The process path {process_path}.
             The window title: {active_window_name}.
             
             The response must be in the following format:
                {{
                    "observations": string[],
                    "title": string,
                    "process_path": string,
                    "application_name": string,
                    "application_category": string
                }}
             """,
            'images': [imageFilename]
        },
    ])
    return response

if __name__ == "__main__":
    window_thread = threading.Thread(target=window_monitor)
    keystroke_thread = threading.Thread(target=keystroke_monitor)

    window_thread.start()
    keystroke_thread.start()

    window_thread.join()
    keystroke_thread.join()
# response = ollama.chat(model='llava', messages=[
#     {
#         'role': 'user',
#         'content': 'What is this application?',
#         'images': [f"{active_window_name}_{int(time.time())}.png"]
#     },
# ])