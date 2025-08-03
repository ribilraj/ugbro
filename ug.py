import os
import re
import time
import mmap
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import tgcrypto
import subprocess
import concurrent.futures
from math import ceil
from utils import progress_bar
from pyrogram import Client, filters
from pyrogram.types import Message
from io import BytesIO
from pathlib import Path  
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
from base64 import b64decode
import math
import m3u8
from urllib.parse import urljoin
from vars import *  # Add this import
from db import Database

db = Database()
# Add this at the top with other imports
TOOLS_DIR = os.path.join(os.path.dirname(__file__), "tools")
MP4DECRYPT = os.path.join(TOOLS_DIR, "mp4decrypt")  # Linux doesn't need .exe extension

def duration(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return float(result.stdout)

def get_mps_and_keys(api_url):
    response = requests.get(api_url)
    response_json = response.json()
    mpd = response_json.get('mpd_url')
    keys = response_json.get('keys')
    return mpd, keys
   
def exec(cmd):
        process = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output = process.stdout.decode()
        print(output)
        return output
        #err = process.stdout.decode()
def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        print("Waiting for tasks to complete")
        fut = executor.map(exec,cmds)
async def aio(url,name):
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url,name):
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka

async def pdf_download(url, file_name, chunk_size=1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name   
   

def parse_vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = []
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",2)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    new_info.append((i[0], i[2]))
            except:
                pass
    return new_info


def vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = dict()
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",3)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    
                    # temp.update(f'{i[2]}')
                    # new_info.append((i[2], i[0]))
                    #  mp4,mkv etc ==== f"({i[1]})" 
                    
                    new_info.update({f'{i[2]}':f'{i[0]}'})

            except:
                pass
    return new_info


async def decrypt_and_merge_video(mpd_url, keys_string, output_path, output_name, quality="720"):
    try:
        output_path = Path(output_path)
        output_path.mkdir(parents=True, exist_ok=True)

        # Verify mp4decrypt exists and is executable
        if not os.path.exists(MP4DECRYPT):
            raise FileNotFoundError(f"mp4decrypt tool not found at {MP4DECRYPT}")
        
        # Make sure mp4decrypt is executable
        try:
            os.chmod(MP4DECRYPT, 0o755)  # Add execute permission
            print(f"Successfully set permissions for {MP4DECRYPT}")
        except Exception as e:
            print(f"Warning: Could not set permissions for mp4decrypt: {str(e)}")

        cmd1 = f'yt-dlp -f "bv[height<={quality}]+ba/b" -o "{output_path}/file.%(ext)s" --allow-unplayable-format --no-check-certificate --external-downloader aria2c "{mpd_url}"'
        print(f"Running command: {cmd1}")
        os.system(cmd1)
        
        avDir = list(output_path.iterdir())
        print(f"Downloaded files: {avDir}")
        print("Decrypting")

        video_decrypted = False
        audio_decrypted = False

        for data in avDir:
            if data.suffix == ".mp4" and not video_decrypted:
                cmd2 = f'"{MP4DECRYPT}" {keys_string} --show-progress "{data}" "{output_path}/video.mp4"'
                print(f"Running command: {cmd2}")
                result = subprocess.run(cmd2, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Error running mp4decrypt: {result.stderr}")
                    raise Exception(f"mp4decrypt failed: {result.stderr}")
                if (output_path / "video.mp4").exists():
                    video_decrypted = True
                data.unlink()
            elif data.suffix == ".m4a" and not audio_decrypted:
                cmd3 = f'"{MP4DECRYPT}" {keys_string} --show-progress "{data}" "{output_path}/audio.m4a"'
                print(f"Running command: {cmd3}")
                result = subprocess.run(cmd3, shell=True, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"Error running mp4decrypt: {result.stderr}")
                    raise Exception(f"mp4decrypt failed: {result.stderr}")
                if (output_path / "audio.m4a").exists():
                    audio_decrypted = True
                data.unlink()

        if not video_decrypted or not audio_decrypted:
            raise FileNotFoundError("Decryption failed: video or audio file not found.")

        cmd4 = f'ffmpeg -i "{output_path}/video.mp4" -i "{output_path}/audio.m4a" -c copy "{output_path}/{output_name}.mp4"'
        print(f"Running command: {cmd4}")
        os.system(cmd4)
        if (output_path / "video.mp4").exists():
            (output_path / "video.mp4").unlink()
        if (output_path / "audio.m4a").exists():
            (output_path / "audio.m4a").unlink()
        
        filename = output_path / f"{output_name}.mp4"

        if not filename.exists():
            raise FileNotFoundError("Merged video file not found.")

        cmd5 = f'ffmpeg -i "{filename}" 2>&1 | grep "Duration"'
        duration_info = os.popen(cmd5).read()
        print(f"Duration info: {duration_info}")

        return str(filename)

    except Exception as e:
        print(f"Error during decryption and merging: {str(e)}")
        raise

async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if proc.returncode == 1:
        return False
    if stdout:
        return f'[stdout]\n{stdout.decode()}'
    if stderr:
        return f'[stderr]\n{stderr.decode()}'

    

def old_download(url, file_name, chunk_size = 1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name


def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"


async def split_file(file_path, chunk_size_mb=2000):
    """Split large file into equal parts"""
    split_files = []  # Initialize split_files list at the start
    
    try:
        file_size = os.path.getsize(file_path)
        chunk_size = chunk_size_mb * 1024 * 1024  # Convert MB to bytes
        
        if file_size > chunk_size:
            num_chunks = math.ceil(file_size / chunk_size)
            base_name = os.path.splitext(file_path)[0]
            ext = os.path.splitext(file_path)[1]
            
            print(f"\nLarge file detected ({file_size / (1024*1024*1024):.2f} GB)")
            print(f"Splitting into {num_chunks} equal parts...")
            
            try:
                # Get video duration using ffprobe
                duration = float(subprocess.check_output([
                    'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                    '-of', 'default=noprint_wrappers=1:nokey=1', file_path
                ]).decode().strip())
                
                segment_duration = duration / num_chunks
                
                for i in range(num_chunks):
                    output_file = f"{base_name}_part{i+1}{ext}"
                    start_time = i * segment_duration
                    
                    print(f"\nCreating part {i+1}/{num_chunks}...")
                    # Optimized ffmpeg command for faster splitting
                    cmd = f'ffmpeg -hide_banner -loglevel error -stats -i "{file_path}" -ss {start_time} -t {segment_duration} -c copy -avoid_negative_ts 1 -movflags +faststart "{output_file}"'
                    subprocess.run(cmd, shell=True)
                    
                    if os.path.exists(output_file):
                        split_files.append(output_file)
                        print(f"Part {i+1} created successfully")
                    else:
                        print(f"Failed to create part {i+1}")
                
                if not split_files:  # If no splits were created successfully
                    print("No split files were created successfully, returning original file")
                    return [file_path]
                    
                return split_files
                
            except Exception as e:
                print(f"Error during file splitting: {str(e)}")
                return [file_path]
        
        return [file_path]  # Return original file if no splitting needed
        
    except Exception as e:
        print(f"Error checking file size: {str(e)}")
        return [file_path]  # Return original file in case of any error

async def fast_download(url, name):
    """Fast direct download implementation without yt-dlp"""
    max_retries = 5
    retry_count = 0
    success = False
    
    while not success and retry_count < max_retries:
        try:
            if "m3u8" in url:
                # Handle m3u8 files
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        m3u8_text = await response.text()
                        
                    playlist = m3u8.loads(m3u8_text)
                    if playlist.is_endlist:
                        # Direct download of segments
                        base_url = url.rsplit('/', 1)[0] + '/'
                        
                        # Download all segments concurrently
                        segments = []
                        async with aiohttp.ClientSession() as session:
                            tasks = []
                            for segment in playlist.segments:
                                segment_url = urljoin(base_url, segment.uri)
                                task = asyncio.create_task(session.get(segment_url))
                                tasks.append(task)
                            
                            responses = await asyncio.gather(*tasks)
                            for response in responses:
                                segment_data = await response.read()
                                segments.append(segment_data)
                        
                        # Merge segments and save
                        output_file = f"{name}.mp4"
                        with open(output_file, 'wb') as f:
                            for segment in segments:
                                f.write(segment)
                        
                        success = True
                        return [output_file]
                    else:
                        # For live streams, fall back to ffmpeg
                        cmd = f'ffmpeg -hide_banner -loglevel error -stats -i "{url}" -c copy -bsf:a aac_adtstoasc -movflags +faststart "{name}.mp4"'
                        subprocess.run(cmd, shell=True)
                        if os.path.exists(f"{name}.mp4"):
                            success = True
                            return [f"{name}.mp4"]
            else:
                # For direct video URLs
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            output_file = f"{name}.mp4"
                            with open(output_file, 'wb') as f:
                                while True:
                                    chunk = await response.content.read(1024*1024)  # 1MB chunks
                                    if not chunk:
                                        break
                                    f.write(chunk)
                            success = True
                            return [output_file]
            
            if not success:
                print(f"\nAttempt {retry_count + 1} failed, retrying in 3 seconds...")
                retry_count += 1
                await asyncio.sleep(3)
                
        except Exception as e:
            print(f"\nError during attempt {retry_count + 1}: {str(e)}")
            retry_count += 1
            await asyncio.sleep(3)
    
    return None

async def download_video(url, cmd, name):
    max_retries = 2  # Reduced retries for faster failure handling
    retry_count = 0
    success = False
    
    while not success and retry_count < max_retries:
        try:
            # Optimize download command with better aria2c parameters
            download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32 -s 16 -k 1M --file-allocation=none --optimize-concurrent-downloads=true"'

            print(f"\n⚡ Downloading...")
            k = subprocess.run(download_cmd, shell=True)
            
            # Check if file exists and has size > 0
            output_file = None
            if os.path.exists(f"{name}.mp4") and os.path.getsize(f"{name}.mp4") > 0:
                output_file = f"{name}.mp4"
                success = True
            elif os.path.exists(name) and os.path.getsize(name) > 0:
                output_file = name
                success = True
            
            if success:
                # Check if file needs to be split (only for files > 2GB)
                if os.path.getsize(output_file) > 2 * 1024 * 1024 * 1024:
                    split_files = await split_file(output_file)
                if len(split_files) > 1:
                    return split_files
                    break
                else:
                    return [output_file]
            
            if not success:
                print(f"\n⚠️ Retry {retry_count + 1}...")
                retry_count += 1
                await asyncio.sleep(2)
            
        except Exception as e:
            print(f"\n❌ Error: {str(e)}")
            retry_count += 1
            await asyncio.sleep(2)
    
    # Final check for file existence
    try:
        if os.path.isfile(name):
            return [name]
        elif os.path.isfile(f"{name}.webm"):
            return [f"{name}.webm"]
        name = name.split(".")[0]
        if os.path.isfile(f"{name}.mkv"):
            return [f"{name}.mkv"]
        elif os.path.isfile(f"{name}.mp4"):
            return [f"{name}.mp4"]
        elif os.path.isfile(f"{name}.mp4.webm"):
            return [f"{name}.mp4.webm"]
        return [name]
    except FileNotFoundError:
        return [name + ".mp4"]


async def send_doc(bot: Client, m: Message, cc, ka, cc1, prog, count, name, channel_id):
    # First send to user
    reply = await bot.send_message(channel_id, f"Downloading pdf:\n<pre><code>{name}</code></pre>")
    time.sleep(1)
    start_time = time.time()
    
    # Send document to user
    sent_doc = await bot.send_document(channel_id, ka, caption=cc1)
    
    # Try forwarding to log channel if configured (don't validate)
    log_channel = db.get_log_channel(bot.me.username)
    if log_channel:
        try:
            await bot.send_document(log_channel, sent_doc.document.file_id, caption=f"#Document\n\nUser: {m.from_user.mention}\nFile: {name}\n\n{cc1}")
        except:
            pass  # Ignore any errors when forwarding to log channel
    
    count+=1
    await reply.delete(True)
    time.sleep(1)
    os.remove(ka)
    time.sleep(3)


def decrypt_file(file_path, key):  
    if not os.path.exists(file_path): 
        return False  

    with open(file_path, "r+b") as f:  
        num_bytes = min(28, os.path.getsize(file_path))  
        with mmap.mmap(f.fileno(), length=num_bytes, access=mmap.ACCESS_WRITE) as mmapped_file:  
            for i in range(num_bytes):  
                mmapped_file[i] ^= ord(key[i]) if i < len(key) else i 
    return True  

async def download_and_decrypt_video(url, cmd, name, key):  
    video_path = await download_video(url, cmd, name)  
    # Safely handle if a list is returned
    if isinstance(video_path, list) and video_path:
        video_path = video_path[0]
    if video_path:  
        decrypted = decrypt_file(video_path, key)  
        if decrypted:  
            print(f"File {video_path} decrypted successfully.")  
            return video_path  
        else:  
            print(f"Failed to decrypt {video_path}.")  
            return None  

async def send_vid(bot: Client, m: Message, cc, filename, thumb, name, prog, channel_id, watermark="UG"):
    # Get log channel ID (don't validate)
    log_channel = db.get_log_channel(bot.me.username)
    
    # Check if filename is a list (split files)
    if isinstance(filename, list) and len(filename) > 1:
        await prog.delete(True)
        await m.reply_text(f"**Large File Detected!**\nUploading in {len(filename)} parts...")
        
        for i, part in enumerate(filename, 1):
            # Generate thumbnail only if not provided or default
            thumbnail = thumb
            if thumb in ["/d", "no"] or not os.path.exists(thumb):
                temp_thumb = f"downloads/thumb_{part}.jpg"
                subprocess.run(f'ffmpeg -i "{part}" -ss 00:00:10 -vframes 1 -q:v 2 -y "{temp_thumb}"', shell=True)
                if os.path.exists(temp_thumb):
                    spaced_text = ' '.join(watermark)
                    text_cmd = f'ffmpeg -i "{temp_thumb}" -vf "drawbox=y=0:color=black@0.5:width=iw:height=200:t=fill,drawtext=fontfile=font.otf:text=\'{spaced_text}\':fontcolor=white:fontsize=90:x=(w-text_w)/2:y=60" -c:v mjpeg -q:v 2 -y "{temp_thumb}"'
                    subprocess.run(text_cmd, shell=True)
                thumbnail = temp_thumb if os.path.exists(temp_thumb) else None
            
            reply = await m.reply_text(f"**Uploading Part {i}/{len(filename)}**")
            dur = int(duration(part))
            start_time = time.time()
            
            try:
                # First send video to user
                sent_video = await bot.send_video(
                    channel_id, 
                    part,
                    caption=f"{cc}\n\nPart {i}/{len(filename)}", 
                    supports_streaming=True,
                    height=720,
                    width=1280,
                    thumb=thumbnail,
                    duration=dur,
                    progress=progress_bar,
                    progress_args=(reply, start_time)
                )
                
                # Try forwarding to log channel
                if log_channel:
                    try:
                        await bot.send_video(
                            log_channel,
                            sent_video.video.file_id,
                            caption=f"**User**: {m.from_user.mention}\n{cc}",
                            supports_streaming=True
                        )
                    except:
                        pass  # Ignore log channel errors
                    
            except Exception as e:
                print(f"Error sending video: {str(e)}")
                # Try sending as document if video fails
                try:
                    sent_doc = await bot.send_document(
                        channel_id,
                        part,
                        caption=f"{cc}\n\nPart {i}/{len(filename)}",
                        progress=progress_bar,
                        progress_args=(reply, start_time)
                    )
                    
                    # Try forwarding document to log channel
                    if log_channel:
                        try:
                            await bot.send_document(
                                log_channel,
                                sent_doc.document.file_id,
                                caption=f"**User**: {m.from_user.mention}\n{cc}",
                            )
                        except:
                            pass  # Ignore log channel errors
                except Exception as e:
                    print(f"Error sending document: {str(e)}")
                
            os.remove(part)
            await reply.delete(True)
            
            if thumb in ["/d", "no"] and os.path.exists(temp_thumb):
                os.remove(temp_thumb)
            
            await asyncio.sleep(1)
        
        await m.reply_text("✅ Upload complete!", quote=True)
        await asyncio.sleep(2)

    else:
        # Handle single file
        if isinstance(filename, list):
            filename = filename[0]
            
        # Generate thumbnail only if not provided or default
        thumbnail = thumb
        if thumb in ["/d", "no"] or not os.path.exists(thumb):
            temp_thumb = f"downloads/thumb_{os.path.basename(filename)}.jpg"
            subprocess.run(f'ffmpeg -i "{filename}" -ss 00:00:10 -vframes 1 -q:v 2 -y "{temp_thumb}"', shell=True)
            if os.path.exists(temp_thumb):
                spaced_text = ' '.join(watermark)
                text_cmd = f'ffmpeg -i "{temp_thumb}" -vf "drawbox=y=0:color=black@0.5:width=iw:height=200:t=fill,drawtext=fontfile=font.otf:text=\'{spaced_text}\':fontcolor=white:fontsize=90:x=(w-text_w)/2:y=60" -c:v mjpeg -q:v 2 -y "{temp_thumb}"'
                subprocess.run(text_cmd, shell=True)
            thumbnail = temp_thumb if os.path.exists(temp_thumb) else None
            
        await prog.delete(True)
        reply = await m.reply_text("**Uploading...**")
          
        dur = int(duration(filename))
        start_time = time.time()

        try:
            # First send video to user
            sent_video = await bot.send_video(
                channel_id,
                filename,
                caption=cc,
                supports_streaming=True,
                height=720,
                width=1280,
                thumb=thumbnail,
                duration=dur,
                progress=progress_bar,
                progress_args=(reply, start_time)
            )
            
           
                    
        except Exception as e:
            print(f"Error sending video: {str(e)}")
            # Try sending as document if video fails
            try:
                sent_doc = await bot.send_document(
                    channel_id,
                    filename,
                    caption=cc,
                    progress=progress_bar,
                    progress_args=(reply, start_time)
                )
                
             
            except Exception as e:
                print(f"Error sending document: {str(e)}")
                    
        os.remove(filename)
        await reply.delete(True)
        
        if thumb in ["/d", "no"] and os.path.exists(temp_thumb):
            os.remove(temp_thumb)
