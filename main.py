import os
import threading
import time
import re
import json
import shutil

import keyboard
import pyautogui
import pytesseract
from PIL import Image

try:
    import pygetwindow as gw
except ImportError:
    gw = None
    print('Warning: pygetwindow not installed. Window auto-move will be skipped.')

# --- CONFIGURATION ---
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

WINDOW_POSITION = (0, 0)
WINDOW_SIZE = (1280, 720)
PAUSE_BETWEEN_ACTIONS = 1.5
DEBUG_SAVE = True
DEBUG_DIR = os.path.join(os.path.dirname(__file__), 'debug')
OCR_SCALE = 3
TESSERACT_DIR = os.path.join(os.path.dirname(__file__), 'tesseract')

PROFILES = {
    'Epic Seven (Native)': {
        'window_title': 'Epic Seven',
        'focus_coord': (475, 560),
        'refresh_coord': (500, 665),
        'scan_subregions': [(788, 223, 27, 26), (788, 270, 27, 26), (788, 317, 27, 26), (788, 363, 27, 26)],
    },
}
# --- END CONFIGURATION ---


def get_tesseract_cmd():
    """Return the path to the bundled tesseract executable or fall back to the default install."""
    exe_name = 'tesseract.exe'
    bundled_path = os.path.join(TESSERACT_DIR, exe_name)
    if os.path.isfile(bundled_path):
        return bundled_path
    if os.name == 'nt':
        default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.isfile(default_path):
            return default_path
    return exe_name


def get_target_window(window_title):
    """Return a window matching `window_title`, or None if not found or unavailable."""
    if gw is None:
        return None
    try:
        wins = gw.getWindowsWithTitle(window_title)
        if wins:
            return wins[0]
        for t in gw.getAllTitles():
            if t and window_title.lower() in t.lower():
                found = gw.getWindowsWithTitle(t)
                if found:
                    return found[0]
        try:
            return gw.getActiveWindow()
        except Exception:
            return None
    except Exception:
        return None


def move_window_to_top_left(window):
    """Restore, move, and resize the target window to the configured bounds."""
    if window is None:
        print('No window found to move to top-left.')
        return

    try:
        if getattr(window, 'isMinimized', False):
            window.restore()
        window.moveTo(*WINDOW_POSITION)
        window.resizeTo(*WINDOW_SIZE)
        print(f"Moved window '{window.title}' to {WINDOW_POSITION} and resized to {WINDOW_SIZE}.")
    except Exception as exc:
        print('Could not move and resize window:', exc)


def focus_game_window(window, focus_coord):
    """Bring the target window to foreground and click a focus coordinate."""
    try:
        if window is not None:
            try:
                if getattr(window, 'isMinimized', False):
                    window.restore()
                window.activate()
            except Exception:
                pass
        time.sleep(0.25)
        pyautogui.click(*focus_coord)
        time.sleep(0.15)
    except Exception as exc:
        print(f'Could not focus game window via click: {exc}')


def resize_for_ocr(image, scale=OCR_SCALE):
    """Return a resized, grayscale image optimized for OCR."""
    try:
        proc = image.convert('L')
        proc = proc.resize((proc.width * scale, proc.height * scale), Image.LANCZOS)
        return proc
    except Exception:
        return image


def configure_tesseract():
    cmd = get_tesseract_cmd()
    pytesseract.pytesseract.tesseract_cmd = cmd
    if cmd and os.path.isfile(cmd):
        print(f'Using Tesseract at: {cmd}')
    else:
        print('Tesseract executable not found in bundle or default path; using system PATH.')


def ocr_region_best_number(image):
    """Return the best numeric token (string) found in `image`, or '' if none."""
    try:
        data = pytesseract.image_to_data(image, config='--psm 6', output_type=pytesseract.Output.DICT)
    except Exception:
        return ''

    best = None
    for i, txt in enumerate(data.get('text', [])):
        if not txt:
            continue
        m = re.search(r"(\d+\s*%?)", txt)
        if not m:
            continue
        num = m.group(1).replace(' ', '')
        try:
            conf = float(data.get('conf', [])[i])
        except Exception:
            conf = -1.0
        if best is None or conf > best[1]:
            best = (num, conf)

    return best[0] if best else ''


def run_stat_refresher(profile_name, status_callback=None):
    """Move the window, focus it, and run a simple OCR scan loop."""

    def update_status(text, color='black'):
        if status_callback:
            status_callback(text, color)

    profile = PROFILES.get(profile_name)
    if profile is None:
        print(f'Unknown profile: {profile_name!r}')
        update_status('Unknown profile', 'red')
        return

    scan_subregions = profile['scan_subregions']
    if not scan_subregions:
        print('Profile has no scan_subregions configured.')
        update_status('No regions configured', 'red')
        return

    print(f'Starting refresher with profile: {profile_name}')
    update_status('Running...', 'orange')

    stop_event = threading.Event()

    def on_esc_pressed(_event):
        print('ESC pressed. Stopping refresher.')
        stop_event.set()

    configure_tesseract()
    keyboard_hook = keyboard.on_press_key('esc', on_esc_pressed)

    target_window = get_target_window(profile['window_title'])
    move_window_to_top_left(target_window)
    focus_game_window(target_window, profile['focus_coord'])

    try:
        while not stop_event.is_set():
            pyautogui.click(*profile['refresh_coord'])
            time.sleep(PAUSE_BETWEEN_ACTIONS)

            values = []
            for idx, region in enumerate(scan_subregions):
                try:
                    img = pyautogui.screenshot(region=region)
                except Exception:
                    img = None

                if img is None:
                    val = ''
                else:
                    proc = resize_for_ocr(img)
                    val = ocr_region_best_number(proc)

                values.append(val)

                if DEBUG_SAVE and img is not None and val == '':
                    try:
                        os.makedirs(DEBUG_DIR, exist_ok=True)
                        base = f'debug_{int(time.time()*1000)}_sub{idx}'
                        proc.save(os.path.join(DEBUG_DIR, f'{base}.png'))
                        data = pytesseract.image_to_data(proc, config='--psm 6', output_type=pytesseract.Output.DICT)
                        with open(os.path.join(DEBUG_DIR, f'{base}_data.json'), 'w', encoding='utf-8') as fh:
                            json.dump(data, fh, ensure_ascii=False, indent=2)
                    except Exception:
                        pass

            print('Scanned values:', values)

            if any(v == '5' for v in values):
                print('Found 5! Stopping.')
                update_status('Success: 5 found', 'green')
                break

            time.sleep(0.1)
    finally:
        if keyboard_hook:
            try:
                keyboard.unhook(keyboard_hook)
            except Exception:
                pass
        stop_event.set()
        if status_callback:
            status_callback('Stopped', 'red')
        print('Refresher stopped.')


if __name__ == '__main__':
    run_stat_refresher('Epic Seven (Native)')
