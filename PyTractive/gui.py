from tkinter import ttk
import tkinter as tk
from tkinter.messagebox import showinfo
import tkinter.simpledialog
from typing import List, Dict
from datetime import datetime

from main import *

root = tk.Tk()
#root.iconbitmap("gui_icon.ico")
root.geometry("300x200")
root.title('PyTractive')

get_GPS_button = ttk.Button(
    root,
    text='Get GPS',
    command=lambda: gps(True)
)
get_GPS_button.grid(column=0, row=3, padx=10, pady=10, sticky=tk.E)

get_pet_button = ttk.Button(
    root,
    text='Get Pet',
    command=lambda: pet(True)
)
get_pet_button.grid(column=1, row=3, padx=10, pady=10, sticky=tk.W)

get_live_button = ttk.Button(
    root,
    text='Get Live',
    command=lambda: new_location(True)
)
get_live_button.grid(column=0, row=4, padx=10, pady=10, sticky=tk.E)

root.mainloop()