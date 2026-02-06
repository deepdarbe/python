import pytube
import os
import time

def download_video(url, folder_path, video_number):
    yt = pytube.YouTube(url)
    stream = yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first()
    if not stream:
        stream = yt.streams.filter(adaptive=True, file_extension='mp4').order_by('resolution').desc().first()
    filesize = stream.filesize
    title = f"{video_number}. {stream.title}.mp4"
    # Fix invalid characters in filename
    for ch in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
        title = title.replace(ch, '')
    print(f"Downloading {title}...")
    download_start = time.time()
    stream.download(output_path=folder_path, filename=title)
    download_end = time.time()
    print(f"{title} was downloaded successfully! - Total time: {(download_end - download_start)/60:.2f} minutes - Download speed: {filesize/(download_end - download_start)/1024/1024:.2f} MB/s")

def download_playlist(url, folder_path):
    playlist = pytube.Playlist(url)
    playlist_title = playlist.title
    print(f"Downloading {playlist_title} playlist...")
    print("="*50)
    video_number = 1
    for url in playlist.video_urls:
        download_video(url, folder_path, video_number)
        print("="*50)
        time.sleep(1)
        video_number += 1

url = input("Enter the URL of the playlist: ")
folder_path = input("Enter the folder path to save the videos: ")

download_playlist(url, folder_path)
