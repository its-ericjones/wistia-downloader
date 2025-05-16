# Wistia Slide Downloader

## Table of Contents
- [Libraries](#libraries)
- [Slide ID Extraction](#slide-id-extraction)
- [Extracting Wistia Embed URLs](#extracting-wistia-embed-urls)
- [Downloading the Wistia Video](#downloading-the-wistia-video)
- [Main Workflow](#main-workflow)
- [Merging Videos](#merging-videos)

## Libraries

### Built-In Libraries
- `os`: Handles filesystem operations such as path management and directory creation.
- `re`: Used for extracting parts of the Wistia URL using regular expressions.
- `json`: Parses the JSON metadata from Wistia.
- `subprocess`: Executes the `ffmpeg` command for merging video files.

### External Libraries
- `requests`: Makes HTTP GET requests for downloading metadata and video content.
- `bs4 (BeautifulSoup)`: Parses HTML to locate slide IDs and extract iframe elements.

## Slide ID Extraction

```python
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

        slide_info.sort(key=lambda x: x[0]) 
        return [slide_id for _, slide_id in slide_info]

    except Exception as e:
        print(f"Error parsing page: {e}")
        return []
```

This function fetches the HTML content from a given page URL and extracts slide IDs in the order determined by their `data-position` attributes.

1. Sends a GET request to the specified `page_url`.
2. Uses BeautifulSoup to parse the returned HTML and locate a `<div>` with the id `"slides"`.
3. Within this container, it finds all nested `<div>` elements with a `data-slide-id` attribute.
4. Collects each `data-slide-id` along with its associated `data-position` (for sorting).
5. Returns a list of slide IDs ordered by `data-position`.

## Extracting Wistia Embedded URLs

```python
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
```

This function looks inside a specific slide's HTML block to locate an embedded Wistia iframe.

1. Fetches the HTML content again.
2. Finds the `<div>` that matches the current slide ID using a CSS selector.
3. Searches for an `<iframe>` inside this `<div>` and checks if its `src` points to a Wistia embedded video.
4. Returns the iframe's `src` value if found; otherwise returns `None`.

## Downloading the Wistia Video

```python
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
```

Given a Wistia iframe embed URL, this function downloads the associated video file.

1. Extracts the hashed video ID using a regular expression.
2. Forms the metadata URL from Wistia using this ID and sends a GET request.
3. Parses the JSON response and searches the `assets` list for the best-quality `.mp4` video link.
4. Downloads the video in chunks to avoid memory overload.
5. If `auto_name` is provided, renames the file using that value.
6. Otherwise, prompts the user to input a filename.
7. Returns the final saved filename.

## Main Workflow
```python
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
```
1. Prompts user for:
   - A URL containing all slides
   - A destination directory for saving downloaded videos
2. Creates the output directory if it doesn't exist.
3. Extracts and sorts all `slide_ids` from the page.
4. Asks the user for auto-numbering:
   - If a prefix is provided, the program will generate filenames like `2.1.mp4`, `2.2.mp4`, etc.
   - Allows an optional suffix to be appended (e.g., `- Overview`).
5. Iterates over each slide ID:
   - Extracts the embed URL
   - Downloads the video
   - Names the file automatically if prefix is provided

## Merging Videos
```python
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
```
If multiple videos were downloaded, the user is asked if they want to merge them into one file.

1. If yes:
   - Prompts for the final merged filename
   - Writes a `video_list.txt` containing paths to all the videos
   - Calls `ffmpeg` with the concat demuxer to merge the videos (combining the media files without re-encoding them)
   - Deletes the list file after merging
   - Asks if video files should be deleted
2. If no:
   - Skips merging