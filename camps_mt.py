import os
import time
import requests
from pydub import AudioSegment
from dotenv import load_dotenv
import mutagen
import tempfile
import shutil
import concurrent.futures

# Load environment variables from .env file
load_dotenv()

# Define the input directory from environment variable
input_dir = os.getenv("INPUT_DIR", "input_directory")

# Slack webhook URL from environment variable
slack_webhook_url = os.getenv(
    "SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/your/webhook/url"
)

desired_bitrate = int(os.getenv("BITRATE", 256))

# Supported audio file extensions
SUPPORTED_EXTENSIONS = [
    ".wav",
    ".flac",
    ".ogg",
    ".aac",
    ".m4a",
    ".wma",
    ".alac",
    ".aiff",
    ".mp3",
]


def get_mp3_bitrate(file_path):
    """
    Get the bitrate of an MP3 file
    """
    try:
        audio = mutagen.File(file_path)
        return int(audio.info.bitrate / 1000)
    except Exception as e:
        print(f"Error checking bitrate for {file_path}: {e}")
        return None


def convert_to_mp3(input_path):
    try:
        audio = AudioSegment.from_file(input_path)
        original_stat = os.stat(input_path)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_output_path = temp_file.name

        audio.export(temp_output_path, format="mp3", bitrate=f"{desired_bitrate}k")

        new_path = os.path.splitext(input_path)[0] + ".mp3"
        original_permissions = os.stat(input_path).st_mode
        original_size = os.path.getsize(input_path)
        new_size = os.path.getsize(temp_output_path)

        try:
            original_metadata = mutagen.File(input_path)
            new_metadata = mutagen.File(temp_output_path)
            if original_metadata and new_metadata:
                new_metadata.update(original_metadata)
                new_metadata.save()
        except Exception as meta_error:
            print(
                f"Warning: Skipping metadata for {input_path} due to error: {meta_error}"
            )

            # Estimate artist and title based on the filename
            filename = os.path.basename(input_path)
            name, _ = os.path.splitext(filename)
            if " - " in name:
                artist, title = name.split(" - ", 1)
                new_metadata["artist"] = artist
                new_metadata["title"] = title
                new_metadata.save()
                print(
                    f"Estimated metadata for {input_path}: Artist - {artist}, Title - {title}"
                )
                send_slack_message(
                    f"Estimated metadata for {input_path}:\nArtist - {artist}, Title - {title}"
                )
            else:
                print(f"Could not estimate metadata for {input_path}")
                send_slack_message(
                    f"Could not estimate metadata for {input_path}. Please check manually."
                )

        shutil.move(temp_output_path, new_path)
        os.chmod(new_path, original_permissions)
        os.chown(new_path, original_stat.st_uid, original_stat.st_gid)

        if input_path != new_path:
            os.remove(input_path)

        print(f"Converted and renamed: {new_path}")
        return original_size - new_size

    except Exception as e:
        print(f"Error converting {input_path} to MP3: {e}")
        send_slack_message(f"Error converting {input_path} to MP3: {e}")
        return 0


def process_file(file_path):
    """
    Process a single file for conversion or metadata update.
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext in SUPPORTED_EXTENSIONS:
        if ext == ".mp3":
            bitrate = get_mp3_bitrate(file_path)

            # Check if metadata is missing and estimate from filename
            audio_file = mutagen.File(file_path, easy=True)
            artist = audio_file.get("artist", [""])[0]
            title = audio_file.get("title", [""])[0]

            if not artist or not title:
                filename = os.path.basename(file_path)
                name, _ = os.path.splitext(filename)

                if " - " in name:
                    estimated_artist, estimated_title = name.split(" - ", 1)
                    if not artist:
                        audio_file["artist"] = estimated_artist
                    if not title:
                        audio_file["title"] = estimated_title
                    audio_file.save()

                    print(
                        f"Estimated metadata for {file_path}: Artist - {estimated_artist}, Title - {estimated_title}"
                    )
                    send_slack_message(
                        f"Estimated metadata for {file_path}:\nArtist - {estimated_artist}, Title - {estimated_title}"
                    )
                else:
                    print(f"Could not estimate metadata for {file_path}")
                    send_slack_message(
                        f"Could not estimate metadata for {file_path}. Please check manually."
                    )

            if bitrate == desired_bitrate or (bitrate and bitrate < desired_bitrate):
                return 0  # No conversion needed

        return convert_to_mp3(file_path)

    return 0


def process_directory(input_dir):
    """
    Process all audio files in a directory using multiple cores.
    """
    converted_count = 0
    total_space_saved = 0
    start_time = time.time()

    files_to_process = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            files_to_process.append(os.path.join(root, file))

    with concurrent.futures.ProcessPoolExecutor() as executor:
        results = list(executor.map(process_file, files_to_process))

    for space_saved in results:
        if space_saved > 0:
            converted_count += 1
            total_space_saved += space_saved

    end_time = time.time()
    duration = end_time - start_time

    if converted_count > 0:
        send_slack_notification(converted_count, duration, total_space_saved)

    print(
        f"Conversion completed! Files converted: {converted_count}, Total space saved: {total_space_saved / (1024 * 1024):.2f} MB, Time taken: {duration:.2f} seconds."
    )


def send_slack_notification(converted_count, duration, total_space_saved):
    """
    Send a Slack notification with the conversion summary.
    """

    send_slack_message(
        f"Audio Conversion Completed!\nFiles Converted: {converted_count}\nTime Taken: {duration:.2f} seconds.\nTotal Space Saved: {total_space_saved / (1024 * 1024):.2f} MB"
    )


def send_slack_message(message):
    """
    Send a Slack notification
    """
    message = {"text": message}
    try:
        response = requests.post(slack_webhook_url, json=message)
        if response.status_code == 200:
            print("Slack notification sent successfully.")
        else:
            print(
                f"Failed to send Slack notification. Status code: {response.status_code}"
            )
    except Exception as e:
        print(f"Error sending Slack notification: {e}")


if __name__ == "__main__":
    process_directory(input_dir)
