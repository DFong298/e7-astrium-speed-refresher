import os
import threading
import time
import re
import json

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

WINDOW_TITLE = 'Epic Seven'
WINDOW_POSITION = (0, 0)
WINDOW_SIZE = (1280, 720)
SCAN_REGION = (795, 220, 20, 170)
FOCUS_COORD = (475, 560)
# Coordinate to click the refresh/reroll button
REFRESH_COORD = (500, 665)
# pause after clicking before scanning (seconds)
PAUSE_BETWEEN_ACTIONS = 1.5
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Debugging: save the scanned image + tesseract data when True
DEBUG_SAVE = True
DEBUG_DIR = os.path.join(os.path.dirname(__file__), 'debug')
# Scale factor to resize OCR input images before scanning
OCR_SCALE = 3
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# Manual per-row scan regions. If you provide the four regions here (list of (x,y,w,h)),
# the refresher will OCR each region in order. Example:
# SCAN_SUBREGIONS = [(770,220,45,40), (770,260,45,40), (770,300,45,40), (770,340,45,40)]
SCAN_SUBREGIONS = [(788, 223, 27, 26), (788, 270, 27, 26), (788, 317, 27, 26), (788, 363, 27, 26)]
# --- END CONFIGURATION ---


def print_available_window_titles():
    """Print available window titles for debugging target selection."""
    if gw is None:
        print('pygetwindow is unavailable.')
        return

    titles = [title for title in gw.getAllTitles() if title]
    if not titles:
        print('No window titles found.')
        return

    print('Available window titles:')
    for index, title in enumerate(titles[:50], start=1):
        print(f'  {index:2d}. {title}')
    if len(titles) > 50:
        print(f'  ...plus {len(titles) - 50} more titles')
def get_target_window():
    """Return a window matching `WINDOW_TITLE`, or None if not found or unavailable.

    Prefers exact matches from `gw.getWindowsWithTitle`, falls back to a partial-title
    search, then to the active window. Returns `None` when `pygetwindow` is not installed.
    """
    if gw is None:
        return None
    try:
        wins = gw.getWindowsWithTitle(WINDOW_TITLE)
        if wins:
            return wins[0]
        # try partial match against available titles
        for t in gw.getAllTitles():
            if t and WINDOW_TITLE.lower() in t.lower():
                found = gw.getWindowsWithTitle(t)
                if found:
                    return found[0]
        # fallback to active window
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


def focus_game_window(window, focus_coord=FOCUS_COORD):
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


def read_scan_region():
    """Capture the configured OCR scan region from the screen."""
    return pyautogui.screenshot(region=SCAN_REGION)



def resize_for_ocr(image, scale=OCR_SCALE):
    """Return a resized, grayscale image optimized for OCR."""
    try:
        proc = image.convert('L')
        proc = proc.resize((proc.width * scale, proc.height * scale), Image.LANCZOS)
        return proc
    except Exception:
        return image


def extract_column_numbers(image):
    """Return a list of numeric strings found in the scanned region, ordered top->bottom.

    Uses Tesseract `image_to_data` to get token positions, extracts the first integer from each token,
    and returns the numbers sorted by token vertical position.
    """
    # Backwards-compatible single-pass extractor kept for callers that expect a flat list.
    proc = resize_for_ocr(image)
    data = pytesseract.image_to_data(proc, config='--psm 6', output_type=pytesseract.Output.DICT)
    texts = data.get('text', [])
    tops = data.get('top', [])
    heights = data.get('height', [])

    entries = []
    for i, t in enumerate(texts):
        if not t:
            continue
        m = re.search(r"(\d+\s*%?)", t)
        if not m:
            continue
        num = m.group(1).replace(' ', '')
        top = tops[i] if i < len(tops) else 0
        h = heights[i] if i < len(heights) else 0
        center_y = top + h / 2
        entries.append((center_y, num))

    entries.sort(key=lambda x: x[0])
    numbers = [num for (_, num) in entries]
    return numbers


def extract_numbers_by_rows(image, row_count=4):
    """Split `image` vertically into `row_count` bands and OCR each band separately.

    Returns a list of length `row_count` with the best numeric token (string) for each band,
    or '' when no numeric token was found.
    """
    w, h = image.size
    row_h = max(1, h // row_count)
    results = []

    for r in range(row_count):
        y0 = r * row_h
        y1 = (r + 1) * row_h if r < row_count - 1 else h
        band = image.crop((0, y0, w, y1))

        proc = resize_for_ocr(band)

        # OCR this band
        data = pytesseract.image_to_data(proc, config='--psm 6', output_type=pytesseract.Output.DICT)

        # find numeric tokens, prefer highest confidence
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

        if best:
            results.append(best[0])
        else:
            results.append('')

        # save per-band debug artifacts only when OCR found nothing for the band
        if DEBUG_SAVE and best is None:
            try:
                os.makedirs(DEBUG_DIR, exist_ok=True)
                base = f'debug_{int(time.time()*1000)}_row{r}'
                band_path = os.path.join(DEBUG_DIR, f'{base}.png')
                proc.save(band_path)
                band_json = os.path.join(DEBUG_DIR, f'{base}_data.json')
                with open(band_json, 'w', encoding='utf-8') as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
            except Exception:
                pass

    return results


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


def run_stat_refresher(status_callback=None):
    """Move the window, focus it, and run a simple OCR scan loop."""

    def update_status(text, color='black'):
        if status_callback:
            status_callback(text, color)

    print('Starting refresher loop with simple OCR scan.')
    update_status('Running...', 'orange')

    stop_event = threading.Event()

    def on_esc_pressed(_event):
        print('ESC pressed. Stopping refresher.')
        stop_event.set()

    keyboard_hook = keyboard.on_press_key('esc', on_esc_pressed)

    target_window = get_target_window()
    move_window_to_top_left(target_window)
    focus_game_window(target_window)

    try:
        while not stop_event.is_set():
            # Step 1: click refresh
            pyautogui.click(*REFRESH_COORD)

            # Step 2: wait variable time for UI to update
            time.sleep(PAUSE_BETWEEN_ACTIONS)

            # Step 3/4: OCR each user-provided subregion if available, otherwise scan SCAN_REGION split into rows
            values = []
            if isinstance(SCAN_SUBREGIONS, (list, tuple)) and len(SCAN_SUBREGIONS) > 0:
                for idx, region in enumerate(SCAN_SUBREGIONS):
                    try:
                        img = pyautogui.screenshot(region=region)
                    except Exception:
                        img = None

                    if img is None:
                        val = ''
                    else:
                        val = ocr_region_best_number(resize_for_ocr(img))

                    values.append(val)

                    # Debug: save per-region image + data only when no value was recorded
                    if DEBUG_SAVE and img is not None and val == '':
                        try:
                            os.makedirs(DEBUG_DIR, exist_ok=True)
                            base = f'debug_{int(time.time()*1000)}_sub{idx}'
                            img_path = os.path.join(DEBUG_DIR, f'{base}.png')
                            img.save(img_path)
                            data = pytesseract.image_to_data(img, config='--psm 6', output_type=pytesseract.Output.DICT)
                            json_path = os.path.join(DEBUG_DIR, f'{base}_data.json')
                            with open(json_path, 'w', encoding='utf-8') as fh:
                                json.dump(data, fh, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
            else:
                print('SCAN_SUBREGIONS is empty. Please set SCAN_SUBREGIONS to your four regions in main.py. Stopping refresher.')
                update_status('No regions configured', 'red')
                stop_event.set()
                break

            print('Scanned values:', values)

            # Step 5: check for '5'
            if any(v == '5' for v in values):
                print('Found 5! Stopping.')
                update_status('Success: 5 found', 'green')
                break

            # Step 6: repeat loop
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
    run_stat_refresher()
