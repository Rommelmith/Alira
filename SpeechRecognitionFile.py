from selenium import webdriver
from selenium.webdriver.common.by import By
from time import sleep, time
import chromedriver_autoinstaller

# Path to your local HTML file
Link = r'C:\Users\romme\PycharmProjects\Alira\voice.html'

# -------------------------
# Chrome options
# -------------------------
chrome_options = webdriver.ChromeOptions()

# We need normal (non-headless) Chrome for real mic access.
# Do NOT enable headless here.
# chrome_options.add_argument("--headless=new")

# Run in background: minimized window
chrome_options.add_argument("--start-minimized")

# Auto-accept mic permission dialog
chrome_options.add_argument("--use-fake-ui-for-media-stream")

# Use real microphone (no fake device)
# chrome_options.add_argument("--use-fake-device-for-media-stream")

# -------------------------
# Initialize Chrome driver
# -------------------------
chromedriver_autoinstaller.install()
driver = webdriver.Chrome(options=chrome_options)
driver.get(Link)
sleep(2)  # let the page load


# -------------------------
# Speech recognition function
# -------------------------
def SpeechRecognition(max_wait: float = 7.0, stable_wait: float = 0.8):
    """
    Wait for you to speak and return the recognized text.

    - max_wait:    ONLY used before you start speaking.
                   If you stay totally silent for max_wait seconds -> returns None.
                   Once any text appears, max_wait is ignored.
    - stable_wait: after text stops changing for this many seconds,
                   we assume you finished speaking and return it.

    Returns:
        - str : final recognized text
        - None: if you never spoke / nothing recognized in max_wait seconds
    """

    # 1) Clear any old output
    try:
        driver.execute_script(
            "document.getElementById('output').textContent = ''"
        )
    except Exception:
        pass

    # 2) Start recognition in the page
    try:
        driver.find_element(By.ID, "start").click()
    except Exception:
        return None

    start_time = time()
    last_text = ""
    last_change_time = None
    got_any_text = False

    while True:
        now = time()

        # Read current text from the page
        try:
            current_text = driver.find_element(By.ID, "output").text.strip()
        except Exception:
            current_text = ""

        if current_text:
            # We have some text -> user has started speaking
            if not got_any_text:
                # First time we see text
                got_any_text = True
                last_text = current_text
                last_change_time = now
            elif current_text != last_text:
                # Text changed while you are speaking
                last_text = current_text
                last_change_time = now

            # Once text has NOT changed for stable_wait seconds -> you stopped speaking
            if last_change_time is not None and (now - last_change_time) >= stable_wait:
                try:
                    driver.find_element(By.ID, "end").click()
                except Exception:
                    pass
                return last_text

        else:
            # No text at all yet -> only case where max_wait applies
            if (not got_any_text) and max_wait is not None and (now - start_time) >= max_wait:
                try:
                    driver.find_element(By.ID, "end").click()
                except Exception:
                    pass
                return None

        # Small sleep to avoid hammering the browser
        sleep(0.1)


# -------------------------
# Test loop (optional)
# -------------------------
if __name__ == "__main__":
    try:
        while True:
            text = SpeechRecognition()

            # If no speech detected, stay silent
            if not text:
                continue

            # You actually spoke -> we print status + text
            print("speaking")
            print(text)

    finally:
        driver.quit()
