import os
import threading
import tkinter as tk
from PIL import Image

from main import PROFILES, run_stat_refresher


def launch_gui():
    """Create a minimal GUI launcher for the stat refresher."""
    root = tk.Tk()
    root.title('Stat Refresher Launcher')
    root.geometry('320x240')
    root.resizable(False, False)

    asset_dir = os.path.join(os.path.dirname(__file__), 'assets')
    png_path = os.path.join(asset_dir, 'chud.png')
    ico_path = os.path.join(asset_dir, 'chud.ico')

    if os.path.isfile(png_path):
        try:
            icon_img = tk.PhotoImage(file=png_path)
            root.iconphoto(True, icon_img)
        except Exception as exc:
            print(f'Could not load PNG icon: {exc}')

        if os.path.isfile(ico_path):
            try:
                root.iconbitmap(ico_path)
            except Exception as exc:
                print(f'Could not load ICO icon: {exc}')
        else:
            try:
                tmp_ico_path = os.path.join(asset_dir, 'tmp_chud.ico')
                img = Image.open(png_path)
                img.save(tmp_ico_path, format='ICO')
                root.iconbitmap(tmp_ico_path)
            except Exception as exc:
                print(f'Could not create ICO fallback: {exc}')
    elif os.path.isfile(ico_path):
        try:
            root.iconbitmap(ico_path)
        except Exception as exc:
            print(f'Could not load ICO icon: {exc}')

    label = tk.Label(root, text='Stat Refresher', font=('Helvetica', 16, 'bold'))
    label.pack(pady=12)

    info = tk.Label(root, text='Click start to run the refresher.\nPress ESC to stop.', justify=tk.CENTER)
    info.pack(pady=8)

    profile_var = tk.StringVar(root)
    profile_var.set(next(iter(PROFILES)))
    profile_menu = tk.OptionMenu(root, profile_var, *PROFILES.keys())
    profile_menu.config(width=24)
    profile_menu.pack(pady=4)

    status_label = tk.Label(root, text='Ready', fg='green')
    status_label.pack(pady=8)

    def on_start():
        status_label.config(text='Running...', fg='orange')
        start_button.config(state=tk.DISABLED)
        profile_menu.config(state=tk.DISABLED)

        def status_callback(text, color):
            status_label.config(text=text, fg=color)
            if text in ('Stopped', 'Success: 5 found'):
                start_button.config(state=tk.NORMAL)
                profile_menu.config(state=tk.NORMAL)

        refresher_thread = threading.Thread(
            target=run_stat_refresher,
            args=(profile_var.get(), status_callback),
            daemon=True,
        )
        refresher_thread.start()

    start_button = tk.Button(root, text='Start Refresh', width=20, command=on_start)
    start_button.pack(pady=12)

    root.mainloop()


if __name__ == '__main__':
    launch_gui()
