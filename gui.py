import os
import sys
import threading
import tkinter as tk
from tkinter import messagebox

try:
    import customtkinter
    from PIL import Image

    from main import PROFILES, run_stat_refresher
except Exception as exc:
    _root = tk.Tk()
    _root.withdraw()
    messagebox.showerror(
        'Startup Error',
        f'Astrium Speed Refresher failed to start because a required component is missing or broken:\n\n{exc}',
    )
    sys.exit(1)

SUBSTAT_DIVISORS = {0: 20, 1: 60, 2: 150}

customtkinter.set_appearance_mode('System')
customtkinter.set_default_color_theme('blue')


def launch_gui():
    """Create a minimal GUI launcher for the stat refresher."""
    root = customtkinter.CTk()
    root.title('Stat Refresher Launcher')
    root.geometry('340x500')
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

    label = customtkinter.CTkLabel(root, text='Astral Forge 5-Speed Refresher', font=customtkinter.CTkFont(size=20, weight='bold'))
    label.pack(pady=12)

    big_chud_path = os.path.join(asset_dir, 'big_chud.png')
    if os.path.isfile(big_chud_path):
        try:
            mascot_pil = Image.open(big_chud_path)
            mascot_pil.thumbnail((160, 160))
            mascot_image = customtkinter.CTkImage(light_image=mascot_pil, dark_image=mascot_pil, size=mascot_pil.size)
            mascot_label = customtkinter.CTkLabel(root, image=mascot_image, text='')
            mascot_label.pack(pady=8)
        except Exception as exc:
            print(f'Could not load mascot image: {exc}')

    info = customtkinter.CTkLabel(root, text='After entering information,\n click start to run the refresher.\nPress ESC to stop early.', justify='center')
    info.pack(pady=8)

    field_width = 175
    label_width = 130

    row_padx = (0, 25)

    profile_row = customtkinter.CTkFrame(root, fg_color='transparent')
    profile_row.pack(pady=4, padx=row_padx)
    customtkinter.CTkLabel(profile_row, text='Client:', width=label_width, anchor='e').pack(side='left', padx=(0, 8))
    profile_var = customtkinter.StringVar(root)
    profile_var.set(next(iter(PROFILES)))
    profile_menu = customtkinter.CTkOptionMenu(profile_row, values=list(PROFILES.keys()), variable=profile_var, width=field_width, anchor='center')
    profile_menu.pack(side='left')

    points_row = customtkinter.CTkFrame(root, fg_color='transparent')
    points_row.pack(pady=4, padx=row_padx)
    customtkinter.CTkLabel(points_row, text='Points to Refresh:', width=label_width, anchor='e').pack(side='left', padx=(0, 8))
    points_entry = customtkinter.CTkEntry(points_row, width=field_width)
    points_entry.pack(side='left')

    locked_row = customtkinter.CTkFrame(root, fg_color='transparent')
    locked_row.pack(pady=4, padx=row_padx)
    customtkinter.CTkLabel(locked_row, text='Substats Locked:', width=label_width, anchor='e').pack(side='left', padx=(0, 8))
    locked_var = customtkinter.StringVar(root, value='0')
    locked_menu = customtkinter.CTkOptionMenu(locked_row, values=['0', '1', '2'], variable=locked_var, width=field_width, anchor='center')
    locked_menu.pack(side='left')

    status_label = customtkinter.CTkLabel(root, text='Ready', text_color='green')
    status_label.pack(pady=8)

    def on_start():
        try:
            points = int(points_entry.get().strip())
            if points < 0:
                raise ValueError
        except ValueError:
            status_label.configure(text='Invalid points value', text_color='red')
            return

        max_iterations = points // SUBSTAT_DIVISORS[int(locked_var.get())]

        status_label.configure(text='Running...', text_color='orange')
        start_button.configure(state='disabled')
        profile_menu.configure(state='disabled')
        points_entry.configure(state='disabled')
        locked_menu.configure(state='disabled')

        def status_callback(text, color):
            def update_ui():
                status_label.configure(text=text, text_color=color)
                if text != 'Running...':
                    start_button.configure(state='normal')
                    profile_menu.configure(state='normal')
                    points_entry.configure(state='normal')
                    locked_menu.configure(state='normal')

            root.after(0, update_ui)

        refresher_thread = threading.Thread(
            target=run_stat_refresher,
            args=(profile_var.get(), status_callback, max_iterations),
            daemon=True,
        )
        refresher_thread.start()

    start_button = customtkinter.CTkButton(root, text='Start Refresh', width=200, command=on_start)
    start_button.pack(pady=12)

    def on_toggle_theme():
        new_mode = 'Dark' if customtkinter.get_appearance_mode() == 'Light' else 'Light'
        customtkinter.set_appearance_mode(new_mode)
        theme_button.configure(text='Light Mode' if new_mode == 'Dark' else 'Dark Mode')

    initial_theme_text = 'Light Mode' if customtkinter.get_appearance_mode() == 'Dark' else 'Dark Mode'
    theme_button = customtkinter.CTkButton(root, text=initial_theme_text, width=200, command=on_toggle_theme)
    theme_button.pack(pady=4)

    root.mainloop()


if __name__ == '__main__':
    launch_gui()
