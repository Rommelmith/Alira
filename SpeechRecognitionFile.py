from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep
from selenium.webdriver.common.by import By
import chromedriver_autoinstaller

# Path to your local HTML file
Link = r'C:\Users\romme\PycharmProjects\Alira\voice.html'

# Chrome options
chrome_options = webdriver.ChromeOptions()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--use-fake-ui-for-media-stream")
chrome_options.add_argument("--use-fake-device-for-media-stream")

# Initialize Chrome driver
chromedriver_autoinstaller.install()
driver = webdriver.Chrome(options=chrome_options)
driver.get(Link)
sleep(2)

# --- keep your existing imports/driver setup above ---

def SpeechRecognition(max_wait=7.0):
    """
    Non-blocking listen: returns transcript string, or None on timeout.
    max_wait: seconds to wait for fresh text before giving up.
    """
    from time import time, sleep

    # 1) Clear any stale text first so we don't return old output
    try:
        driver.execute_script("document.getElementById('output').textContent = ''")
    except Exception:
        pass

    # 2) Start recognition
    driver.find_element(by=By.ID, value="start").click()
    print("Listening....")

    deadline = time() + max_wait
    last_text = ""

    # 3) Poll for new text until timeout
    while time() < deadline:
        try:
            txt = driver.find_element(by=By.ID, value="output").text.strip()
        except Exception:
            txt = ""

        # New non-empty text? stop and return it
        if txt and txt != last_text:
            driver.find_element(by=By.ID, value="end").click()
            return txt

        last_text = txt
        sleep(0.2)

    # 4) Timed out: stop and return None so caller can re-check session
    try:
        driver.find_element(by=By.ID, value="end").click()
    except Exception:
        pass
    return None

if __name__ == "__main__":
    try:
        while True:
            Text = SpeechRecognition()
            print(Text)
    finally:
        driver.quit()