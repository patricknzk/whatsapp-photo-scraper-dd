"""
Dog Dayz Silvan Photo Scraper

Issue: Manually searching through photos of dogs uploaded by staff in a whatsapp groupchat. Correctly identifying relevant images then saving them all while seeing only 2-3 photos at a time (limitation due to whatsapp user interface).
       Clients rely on seeing their dogs happy and healthy which is shown and supported by the photos taken by staff. Quickly sorting these images allow for more time spent on more important things, such as planning the next day/week. 

Solution: Automatic web scraper which downloads all uploaded photos of the current day, saved onto your desktop, sorted by date, and name of the dog in image.

Author: Patrick Naumczyk
"""

import os
import re
import base64
import requests
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

# Directory setup for "Silvan Dog Dayz Photos"
base_directory = os.path.join(os.path.expanduser("~"), "Desktop", "Silvan Dog Dayz Photos")
today_date = datetime.now().strftime("%Y-%m-%d")
today_directory = os.path.join(base_directory, f"Dog Photos {today_date}")
os.makedirs(today_directory, exist_ok=True)

# Helper: Generate a unique file name
def get_unique_filename(folder_path, base_name, extension=".jpeg"):
    counter = 1
    unique_name = base_name
    while os.path.exists(os.path.join(folder_path, unique_name + extension)):
        unique_name = f"{base_name} {counter}"
        counter += 1
    return unique_name + extension

# Helper: Remove emojis from text
def remove_emojis(text):
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text)

# Helper: Determine if the message is likely a name
def is_name(message):
    cleaned_message = remove_emojis(message)
    if any(char in cleaned_message for char in ["?", ".", "!"]):
        return False
    return len(cleaned_message) <= 25

# Helper: Extract date and time from a message
def extract_date_time(message_element):
    date_time_text = message_element.get_attribute("data-pre-plain-text")
    if date_time_text and "[" in date_time_text and "]" in date_time_text:
        datetime_part = date_time_text.split("]")[0].strip("[")
        for date_format in ("%H:%M, %d/%m/%Y", "%H:%M, %m/%d/%Y"):
            try:
                return datetime.strptime(datetime_part, date_format)
            except ValueError:
                continue
    return None

# Initialize WebDriver
driver = webdriver.Edge()
driver.get("https://web.whatsapp.com")
print("Please scan the QR code to log in to WhatsApp Web.")

# Wait until WhatsApp Web loads
try:
    WebDriverWait(driver, 300).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#pane-side")))
    print("Login successful. Proceeding...")
except Exception as e:
    print("Login failed or timed out.")
    driver.quit()
    exit()

# Search for the chat
chat_name = "Silvan Photos"
search_box = driver.find_element(By.CSS_SELECTOR, "div[contenteditable='true']")
search_box.send_keys(chat_name)
search_box.send_keys(Keys.RETURN)
time.sleep(2)

# Search Phase
current_date = datetime.now().date()
photo_data = []
found_first_photo = False

while not found_first_photo:
    message_rows = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
    for message in reversed(message_rows):
        try:
            metadata_element = message.find_element(By.CSS_SELECTOR, "div[data-pre-plain-text]")
            metadata = metadata_element.get_attribute("data-pre-plain-text")

            message_content = message.find_element(By.CSS_SELECTOR, ".selectable-text.copyable-text").text
            message_content = remove_emojis(message_content)

            if not is_name(message_content):
                continue

            # Stop if a message from the previous day is found
            message_datetime = extract_date_time(metadata_element)
            if message_datetime and message_datetime.date() != current_date:
                print(f"Found photo from the previous day ({message_datetime.date()}). Stopping search.")
                found_first_photo = True
                break
        except Exception as e:
            print(f"Error processing message: {e}")

    if not found_first_photo:
        initial_message_count = len(driver.find_elements(By.CSS_SELECTOR, "div[role='row']"))
        chat_container = driver.find_element(By.CSS_SELECTOR, "#main")
        ActionChains(driver).move_to_element(chat_container).send_keys(Keys.PAGE_UP).perform()
        try:
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, "div[role='row']")) >= initial_message_count
            )
            time.sleep(2)
        except Exception as e:
            print(f"Warning: No new messages loaded. Error: {e}")
            break

time.sleep(5)

# Reinitialize message_rows
message_rows = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")
new_photo_data = []

# Build dictionary based on reinitialized message_rows
for message in reversed(message_rows):  # Start from the most recent message
    try:
        metadata_element = message.find_element(By.CSS_SELECTOR, "div[data-pre-plain-text]")
        metadata = metadata_element.get_attribute("data-pre-plain-text")

        message_content = message.find_element(By.CSS_SELECTOR, ".selectable-text.copyable-text").text
        message_content = remove_emojis(message_content)
        message_content = message_content.replace("/", "-").replace("\\", "-").strip()

        if not is_name(message_content):
            continue

        print(f"Photos found: {message_content}")

        if "img" in message.get_attribute("innerHTML"):
            image_element = message.find_element(By.CSS_SELECTOR, "img[src]")
            img_url = image_element.get_attribute("src")

            new_photo_data.append({
                "url": img_url,
                "message_content": message_content,
                "timestamp": metadata
            })

    except Exception as e:
        print(f"Error processing message: {e}")

print("Finished building new photo_data dictionary. Starting download phase...")

# Download phase
for photo in new_photo_data:
    img_url = photo["url"]
    message_content = photo["message_content"]
    message_content = remove_emojis(message_content)
    dog_folder = os.path.join(today_directory, message_content)
    os.makedirs(dog_folder, exist_ok=True)

    # Generate a unique file name for the photo
    sanitized_file_name = message_content.replace("/", "-").replace("\\", "-").strip()
    unique_file_name = get_unique_filename(dog_folder, sanitized_file_name)
    save_path = os.path.join(dog_folder, unique_file_name)

    if img_url.startswith("blob:"):
        # Handle blob URLs
        try:
            blob_element = driver.find_element(By.CSS_SELECTOR, f"img[src='{img_url}']")
            blob_data = driver.execute_script("""
                let img = arguments[0];
                try {
                    let canvas = document.createElement('canvas');
                    canvas.width = img.naturalWidth;
                    canvas.height = img.naturalHeight;
                    let ctx = canvas.getContext('2d');
                    ctx.drawImage(img, 0, 0);
                    return canvas.toDataURL('image/jpeg').split(',')[1];
                } catch (error) {
                    return null;
                }
            """, blob_element)
            if blob_data:
                with open(save_path, "wb") as file:
                    file.write(base64.b64decode(blob_data))
                print(f"Blob image saved to {save_path}")
        except Exception as e:
            print(f"Error processing blob image: {e}")

    elif img_url.startswith("https://"):
        # Handle direct https URLs
        try:
            img_data = requests.get(img_url).content
            with open(save_path, "wb") as file:
                file.write(img_data)
            print(f"Image saved to {save_path}")
        except Exception as e:
            print(f"Failed to download image from {img_url}: {e}")

print("Download complete. Please check your desktop folder 'Silvan Dog Dayz Photos'. Window will close in 1 minute.")
time.sleep(60)

# Close the WebDriver
driver.quit()