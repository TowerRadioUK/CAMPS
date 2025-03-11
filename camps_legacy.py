import os
import time
import requests
from pydub import AudioSegment
from dotenv import load_dotenv
import mutagen
import tempfile
import shutil

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
    """
    Convert an audio file to MP3 format while preserving metadata
    """
    try:
        # Load the audio file
        audio = AudioSegment.from_file(input_path)

        # Apply the original owner to the new file
        original_stat = os.stat(input_path)

        # Create a temporary file in the system temp directory
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_output_path = temp_file.name

        # Export as MP3
        audio.export(temp_output_path, format="mp3", bitrate=f"{desired_bitrate}k")

        # Define the new path with .mp3 extension
        new_path = os.path.splitext(input_path)[0] + ".mp3"

        # Get the original file permissions
        original_permissions = os.stat(input_path).st_mode

        # Get the original and new file sizes
        original_size = os.path.getsize(input_path)
        new_size = os.path.getsize(temp_output_path)

        # Preserve metadata
        original_metadata = mutagen.File(input_path)
        new_metadata = mutagen.File(temp_output_path)
        new_metadata.update(original_metadata)
        new_metadata.save()

        # Replace the original file with the converted file
        shutil.move(temp_output_path, new_path)

        # Apply the original file permissions to the new file
        os.chmod(new_path, original_permissions)
        os.chown(new_path, original_stat.st_uid, original_stat.st_gid)

        if input_path != new_path:
            # Delete the original file
            os.remove(input_path)

        print(f"Converted and renamed: {new_path}")
        return original_size - new_size
    except Exception as e:
        print(f"Error converting {input_path}: {e}")

        message = {"text": f"Error converting {input_path} to MP3: {e}"}
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

        return 0


def process_directory(input_dir):
    """
    Process all audio files in a directory
    """
    converted_count = 0
    total_space_saved = 0
    start_time = time.time()

    for root, _, files in os.walk(input_dir):
        for file in files:
            # Get the file extension
            ext = os.path.splitext(file)[1].lower()
            if ext in SUPPORTED_EXTENSIONS:
                # Define full input path
                input_path = os.path.join(root, file)

                # If it's an MP3, check its bitrate
                if ext == ".mp3":
                    bitrate = get_mp3_bitrate(input_path)
                    if bitrate == desired_bitrate:
                        continue
                    elif bitrate and bitrate < desired_bitrate:
                        print(f"Lower bitrate than expected for {file}: {bitrate}kbps")
                        continue

                # Convert the file to MP3 and rename it
                space_saved = convert_to_mp3(input_path)
                if space_saved > 0:
                    converted_count += 1
                    total_space_saved += space_saved

    end_time = time.time()
    duration = end_time - start_time

    if converted_count != 0:
        # Send Slack notification
        send_slack_notification(converted_count, duration, total_space_saved)

    print(
        f"Conversion and renaming completed! Total space saved: {total_space_saved / (1024 * 1024):.2f} MB"
    )


def send_slack_notification(converted_count, duration, total_space_saved):
    """
    Send a Slack notification with the number of files converted, the duration, and the total space saved.
    """

    message = {
        "text": f"Audio Conversion Completed!\nFiles Converted/Modified: {converted_count}\nTime Taken: {duration:.2f} seconds.\nTotal Space Saved: {total_space_saved / (1024 * 1024):.2f} MB"
    }
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
    # Process the input directory
    process_directory(input_dir)
