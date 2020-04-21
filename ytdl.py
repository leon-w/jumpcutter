from pytube import YouTube
from urllib import parse

def sanatize_title(title, fallback="_"):
    return "".join(map(lambda c: c if ord(c) < 128 else fallback, title))

def is_youtube_url(url):
    try:
        o = parse.urlparse(url)
        return o.hostname in ["youtu.be", "youtube.com", "youtube.de"]
    except:
        return False

def download_video(url, progress_callback=print, interval=10):
    yt = YouTube(url)
    title = sanatize_title(yt.title)

    global loaded_bytes, last_print
    loaded_bytes = 0
    last_print = 0

    def on_update(_stream, _chunk, remaining):
        global loaded_bytes, last_print
        percentage = int((loaded_bytes / (remaining + loaded_bytes)) * 100)
        if progress_callback and percentage >= last_print:
            progress_callback(percentage)
            last_print += interval
        loaded_bytes += len(_chunk)

    yt.register_on_progress_callback(on_update)

    return yt.streams.filter(progressive=True, file_extension="mp4").order_by("resolution").desc().first().download(filename=title)
