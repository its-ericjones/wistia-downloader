import requests
import re
import json
import os
import subprocess
from bs4 import BeautifulSoup

def extract_ordered_slide_ids_from_page(page_url):
    try:
        print(f"Fetching: {page_url}")
        response = requests.get(page_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        slides_container = soup.find("div", id="slides")
        if not slides_container:
            print("No <div id='slides'> found.")
            return []

        slide_divs = slides_container.find_all("div", attrs={"data-slide-id": True})
        slide_info = []

        for div in slide_divs:
            slide_id = div["data-slide-id"]
            try:
                position = int(div.get("data-position", 0))
            except ValueError:
                position = 0
            slide_info.append((position, slide_id))

        slide_info.sort(key=lambda x: x[0])  # sort by data-position
        return [slide_id for _, slide_id in slide_info]

    except Exception as e:
        print(f"Error parsing page: {e}")
        return []

def extract_wistia_from_div(page_url, slide_id):
    try:
        response = requests.get(page_url)
        soup = BeautifulSoup(response.text, "html.parser")
        selector = f'div[data-slide-id="{slide_id}"]'
        div = soup.select_one(selector)
        if not div:
            print(f"No div found for slide ID {slide_id}")
            return None
        iframe = div.find("iframe")
        if iframe and "fast.wistia.net/embed/iframe" in iframe.get("src", ""):
            return iframe["src"]
        print(f"No Wistia iframe found for slide ID {slide_id}")
        return None
    except Exception as e:
        print(f"Error extracting Wistia iframe: {e}")
        return None

def download_wistia_video(embed_url, output_dir, auto_name=None):
    match = re.search(r'iframe/([a-zA-Z0-9]+)', embed_url)
    if not match:
        print(f"Invalid Wistia URL: {embed_url}")
        return None

    hashed_id = match.group(1)
    metadata_url = f"https://fast.wistia.com/embed/medias/{hashed_id}.json"
    temp_filename = os.path.join(output_dir, f"temp_{hashed_id}.mp4")

    response = requests.get(metadata_url)
    if response.status_code != 200:
        print(f"Failed to retrieve metadata for {embed_url}")
        return None

    data = response.json()
    assets = data.get('media', {}).get('assets', [])
    video_url = None
    max_quality = 0
    for asset in assets:
        if asset.get("type") == "original" or asset.get("content_type") == "video/mp4":
            if asset.get("width", 0) > max_quality:
                max_quality = asset["width"]
                video_url = asset["url"]

    if not video_url:
        print(f"No downloadable video found for {embed_url}")
        return None

    print("Downloading video...")
    video_response = requests.get(video_url, stream=True)
    with open(temp_filename, "wb") as file:
        for chunk in video_response.iter_content(chunk_size=1024):
            file.write(chunk)

    if auto_name:
        final_name = os.path.join(output_dir, f"{auto_name}.mp4")
        os.rename(temp_filename, final_name)
        print(f"Saved as: {final_name}")
        return final_name
    else:
        new_name = input("Enter a name for this video (without extension): ").strip()
        final_name = os.path.join(output_dir, f"{new_name}.mp4")
        os.rename(temp_filename, final_name)
        return final_name

# Main workflow
print("Wistia Slide Downloader")
page_url = input("Enter the URL of the page that contains all slides: ").strip()

# Destination directory
output_dir = input("Enter the directory where videos should be saved: ").strip()
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Created directory: {output_dir}")

slide_ids = extract_ordered_slide_ids_from_page(page_url)
if not slide_ids:
    print("No valid slide IDs to process. Exiting.")
    exit()

prefix = input("Enter a prefix number for auto-naming (e.g., 2), or press Enter to name manually: ").strip()
suffix = ""
if prefix:
    suffix = input("Enter optional text to append after each number (e.g., '- Overview'), or press Enter for none: ")

auto_numbering = bool(prefix)
counter = 1
video_files = []

for slide_id in slide_ids:
    print(f"\nProcessing slide ID {slide_id}...")
    embed_url = extract_wistia_from_div(page_url, slide_id)
    if embed_url:
        auto_name = f"{prefix}.{counter}{suffix}" if auto_numbering else None
        result = download_wistia_video(embed_url, output_dir, auto_name)
        if result:
            video_files.append(result)
            if auto_numbering:
                counter += 1

if len(video_files) > 1:
    merge = input("\nMerge all videos into a single file? (y/n): ").strip().lower()
    if merge == "y":
        merge_name = input("Enter a name for the final merged video (without extension): ").strip()
        list_file_path = os.path.join(output_dir, "video_list.txt")
        with open(list_file_path, "w") as f:
            for fpath in video_files:
                f.write(f"file '{fpath}'\n")
        merged_path = os.path.join(output_dir, f"{merge_name}.mp4")
        subprocess.run(["ffmpeg", "-f", "concat", "-safe", "0", "-i", list_file_path, "-c", "copy", merged_path])
        os.remove(list_file_path)
        print(f"Merged video saved as: {merged_path}")

        cleanup = input("Delete individual video files? (y/n): ").strip().lower()
        if cleanup == "y":
            for f in video_files:
                os.remove(f)
            print("Deleted individual files. Only merged file remains.")
    else:
        print("Videos downloaded separately. No merge performed.")
else:
    print("Single video downloaded. Merge skipped.")

print("\nComplete!.")