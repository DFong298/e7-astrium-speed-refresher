import pyautogui
import time

print("=" * 50)
print("MOUSE TRACKER RUNNING")
print("Hover over your targets. Coordinates print every 1.5 seconds.")
print("Press Ctrl+C in the terminal to stop.")
print("=" * 50)

try:
    while True:
        x, y = pyautogui.position()
        print(f"X: {x:4d} | Y: {y:4d}")
        time.sleep(1.5)
except KeyboardInterrupt:
    print("\nTracker stopped.")