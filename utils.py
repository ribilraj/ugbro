import random  
import time  
import math  
import os  
from vars import CREDIT  
from pyrogram.errors import FloodWait  
from datetime import datetime,timedelta  

class Timer:  
    def __init__(self, time_between=5):  
        self.start_time = time.time()  
        self.time_between = time_between  

    def can_send(self):  
        if time.time() > (self.start_time + self.time_between):  
            self.start_time = time.time()  
            return True  
        return False  

#lets do calculations  
def hrb(value, digits= 2, delim= "", postfix=""):  
    """Return a human-readable file size.  
    """  
    if value is None:  
        return None  
    chosen_unit = "B"  
    for unit in ("KB", "MB", "GB", "TB"):  
        if value > 1000:  
            value /= 1024  
            chosen_unit = unit  
        else:  
            break  
    return f"{value:.{digits}f}" + delim + chosen_unit + postfix  

def hrt(seconds, precision = 0):  
    """Return a human-readable time delta as a string.  
    """  
    pieces = []  
    value = timedelta(seconds=seconds)  

    if value.days:  
        pieces.append(f"{value.days}day")  

    seconds = value.seconds  

    if seconds >= 3600:  
        hours = int(seconds / 3600)  
        pieces.append(f"{hours}hr")  
        seconds -= hours * 3600  

    if seconds >= 60:  
        minutes = int(seconds / 60)  
        pieces.append(f"{minutes}min")  
        seconds -= minutes * 60  

    if seconds > 0 or not pieces:  
        pieces.append(f"{seconds}sec")  

    if not precision:  
        return "".join(pieces)  

    return "".join(pieces[:precision])  

timer = Timer()  

async def progress_bar(current, total, reply, start):
    if timer.can_send():
        now = time.time()
        diff = now - start
        if diff < 1:
            return

        perc = f"{current * 100 / total:.1f}%"
        
        # Modern progress bar with emojis
        bar_length = 10
        filled_length = int(current * bar_length / total)
        remaining_length = bar_length - filled_length
        
        # Using minimal design
        filled = "█" * filled_length
        remaining = "░" * remaining_length
        progress_bar = f"{filled}{remaining}"

        try:
            await reply.edit(
                f"**Uploading... {perc}**\n"
                f"`{progress_bar}`"
            )
        except FloodWait as e:
            time.sleep(e.x)