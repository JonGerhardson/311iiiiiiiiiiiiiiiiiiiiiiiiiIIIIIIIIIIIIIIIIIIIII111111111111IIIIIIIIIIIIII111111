import os
import re
import time
import random
import logging
import requests
import csv
import json
import signal
import sys
import html2text
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException
from urllib3.exceptions import MaxRetryError, NameResolutionError
import undetected_chromedriver as uc
from selenium_stealth import stealth
from fake_useragent import UserAgent

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("scraper.log"),
        logging.StreamHandler()
    ]
)

# Constants
RATE_LIMIT_DELAY = (2, 5)  # Random delay range in seconds
OUTLIERS_FILE = "outliers.csv"
FAILED_URLS_FILE = "failed_urls.csv"  # Changed to CSV
MAX_RETRIES = 2
USER_AGENT_ROTATION = 5  # Rotate user agent every N requests
STATE_FILE = "scraper_state.json"  # File to save progress

# Global trackers
last_request_time = {}
request_count = 0
ua = UserAgent()

# State management
state = {
    "processed_urls": set(),  # URLs that have been processed
    "blocked_domains": set(),  # Domains blocked by Cloudflare
    "current_index": 0         # Index of the current URL being processed
}

def save_state():
    """Save the current state to a file"""
    try:
        # Convert sets to lists for JSON serialization
        state_to_save = {
            "processed_urls": list(state["processed_urls"]),
            "blocked_domains": list(state["blocked_domains"]),
            "current_index": state["current_index"]
        }
        
        with open(STATE_FILE, "w") as f:
            json.dump(state_to_save, f)
        logging.info("Progress saved successfully.")
    except Exception as e:
        logging.error(f"Failed to save state: {str(e)}")

def load_state():
    """Load the saved state from a file"""
    global state
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                loaded_state = json.load(f)
                # Convert lists back to sets
                state["processed_urls"] = set(loaded_state.get("processed_urls", []))
                state["blocked_domains"] = set(loaded_state.get("blocked_domains", []))
                state["current_index"] = loaded_state.get("current_index", 0)
            logging.info("Loaded previous progress.")
    except Exception as e:
        logging.error(f"Failed to load state: {str(e)}")

def handle_interrupt(signum, frame):
    """Handle script interruption (e.g., Ctrl+C)"""
    logging.info("Interrupt received. Saving progress...")
    save_state()
    sys.exit(0)

# Register interrupt handler
signal.signal(signal.SIGINT, handle_interrupt)

def init_driver():
    """Initialize ChromeDriver with automatic version detection"""
    try:
        options = uc.ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Initialize the driver
        driver = uc.Chrome(
            options=options,
            headless=True,
            use_subprocess=True  # Important for proper version detection
        )
        
        # Apply stealth configurations
        stealth(driver,
               languages=["en-US", "en"],
               vendor="Google Inc.",
               platform="Win32",
               webgl_vendor="Intel Inc.",
               renderer="Intel Iris OpenGL Engine",
               fix_hairline=True)
        
        return driver
    except Exception as e:
        logging.error(f"Driver initialization failed: {str(e)}")
        raise

def get_domain_name(url):
    parsed = urlparse(url)
    domain = parsed.netloc
    return domain.lstrip("www.") if domain.startswith("www.") else domain

def amend_ecode360_url(url):
    if "ecode360.com" in url:
        guid = url.split("/")[-1]
        return f"https://ecode360.com/print/{guid}?guid={guid}"
    return url

def handle_cloudflare(driver):
    """Check for Cloudflare protection and attempt mitigation"""
    try:
        # Check common Cloudflare challenge indicators
        challenge_indicators = [
            (By.ID, "cf-challenge-wrap"),
            (By.CSS_SELECTOR, ".cf-error-title"),
            (By.XPATH, "//*[contains(text(), 'Cloudflare')]")
        ]
        
        if any(driver.find_elements(*indicator) for indicator in challenge_indicators):
            logging.warning("Cloudflare challenge detected")
            return True
            
        # Check for browser validation page
        if "Checking your browser" in driver.page_source:
            logging.warning("Cloudflare browser check detected")
            time.sleep(5)  # Wait for validation to complete
            return True
            
        return False
    except WebDriverException as e:
        logging.error(f"Cloudflare check failed: {str(e)}")
        return True

def scrape_links(driver, url):
    """Scrape links from a page, returning only PDFs if total links > 10"""
    try:
        # Rotate user agent periodically
        global request_count
        request_count += 1
        if request_count % USER_AGENT_ROTATION == 0:
            driver.execute_cdp_cmd('Network.setUserAgentOverride', {
                "userAgent": ua.random
            })
        
        driver.get(url)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Check for Cloudflare protection
        if handle_cloudflare(driver):
            raise ConnectionAbortedError("Cloudflare protection triggered")
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        all_links = []
        pdf_links = []
        
        if get_domain_name(url) != "ecode360.com":
            for link in soup.find_all("a", href=True):
                href = link["href"]
                full_url = urljoin(url, href)
                if href.lower().endswith(".pdf") or "DocumentCenter" in href:
                    pdf_links.append(("pdf", full_url))
                else:
                    all_links.append(("html", full_url))
        
        # Return only PDFs if total links exceed 10
        if len(all_links) + len(pdf_links) > 10:
            logging.info(f"Found {len(pdf_links)} PDFs (skipping {len(all_links)} non-PDF links)")
            return pdf_links
        else:
            logging.info(f"Found {len(all_links) + len(pdf_links)} links")
            return all_links + pdf_links

    except Exception as e:
        logging.error(f"Error scraping {url}: {str(e)}")
        return []

def download_pdf(url, download_dir, retries=MAX_RETRIES):
    try:
        filename = os.path.join(download_dir, url.split("/")[-1].split("?")[0])
        if os.path.exists(filename):
            logging.info(f"Skipping existing file: {filename}")
            return

        domain = get_domain_name(url)
        if domain in last_request_time:
            delay = random.uniform(*RATE_LIMIT_DELAY)
            elapsed = time.time() - last_request_time[domain]
            if elapsed < delay:
                time.sleep(delay - elapsed)
        last_request_time[domain] = time.time()

        for attempt in range(retries):
            try:
                response = requests.get(url, stream=True, timeout=10)
                response.raise_for_status()
                with open(filename, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                logging.info(f"Downloaded: {filename}")
                return
            except Exception as e:
                if attempt == retries - 1:
                    raise
                time.sleep(random.uniform(2, 5))

    except Exception as e:
        logging.error(f"Failed to download {url}: {str(e)}")
        raise

def sanitize_folder_name(name):
    name = re.sub(r'(Town of [\w\s]+, MA)(?= \1)', '', name).strip()
    return re.sub(r'[\\/*?:"<>|]', "", name)

def extract_main_content(soup):
    for tag in ["main", "article"]:
        content = soup.find(tag)
        if content: return content
    for cls in ["content", "main-content", "body", "post-content"]:
        content = soup.find("div", class_=cls)
        if content: return content
    return soup.find("body")

def scrape_html_content(url, download_dir):
    try:
        domain = get_domain_name(url)
        if domain in last_request_time:
            delay = random.uniform(*RATE_LIMIT_DELAY)
            elapsed = time.time() - last_request_time[domain]
            if elapsed < delay:
                time.sleep(delay - elapsed)
        last_request_time[domain] = time.time()

        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        if domain == "ecode360.com":
            title = sanitize_folder_name(soup.find("title").get_text().strip())
            download_dir = os.path.join(download_dir, title)
            os.makedirs(download_dir, exist_ok=True)

        main_content = extract_main_content(soup)
        if not main_content:
            raise ValueError("No main content found")

        converter = html2text.HTML2Text()
        converter.ignore_links = True
        markdown = converter.handle(str(main_content))
        
        filename = os.path.join(download_dir, f"{url.split('/')[-1].split('?')[0]}.md")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(markdown)
        logging.info(f"Saved Markdown: {filename}")

    except Exception as e:
        logging.error(f"Error scraping {url}: {str(e)}")
        raise

def read_urls_from_csv(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return [(row[0].strip(), row[1].strip()) for row in csv.reader(f) if len(row) == 2]
    except Exception as e:
        logging.error(f"CSV read error: {str(e)}")
        return []

def log_outlier(city, url):
    """Log outlier URLs in CSV format matching urls.csv"""
    with open(OUTLIERS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([city, url])

def log_failed_url(city, url, error):
    """Log failed URLs in CSV format with city, url, and error"""
    with open(FAILED_URLS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([city, url, error])

def create_boston_code_file(directory):
    content = """If you dance the same and dress the same
it won't be long 'til you are the same
You look the same and act the same
there's nothing new and you're to blame
This is Boston not L.A.
This is Boston fuck L.A."""
    path = os.path.join(directory, "boston_code.txt")
    with open(path, "w") as f:
        f.write(content)
    logging.info(f"Created Boston code file: {path}")

def main():
    base_dir = "downloaded_content"
    os.makedirs(base_dir, exist_ok=True)
    
    # Initialize CSV files with headers
    with open(OUTLIERS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["city", "url"])  # Headers for outliers
    
    with open(FAILED_URLS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["city", "url", "error"])  # Headers for failed URLs

    # Load previous state
    load_state()

    driver = None

    try:
        city_urls = read_urls_from_csv("urls.csv")
        
        # Skip already processed URLs
        for i in range(state["current_index"], len(city_urls)):
            city, url = city_urls[i]
            state["current_index"] = i  # Update progress

            if url in state["processed_urls"]:
                logging.info(f"Skipping already processed URL: {url}")
                continue

            city_dir = os.path.join(base_dir, city)
            os.makedirs(city_dir, exist_ok=True)

            if city.lower() == "boston":
                create_boston_code_file(city_dir)
                state["processed_urls"].add(url)  # Mark as processed
                save_state()
                continue

            amended_url = amend_ecode360_url(url)
            domain = get_domain_name(amended_url)

            if domain in state["blocked_domains"]:
                log_failed_url(city, amended_url, "Blocked domain")
                state["processed_urls"].add(url)  # Mark as processed
                save_state()
                continue

            retries = MAX_RETRIES
            while retries > 0:
                try:
                    if not driver:
                        driver = init_driver()

                    logging.info(f"Processing {city} - {amended_url}")
                    
                    if amended_url.lower().endswith(".pdf"):
                        download_pdf(amended_url, city_dir)
                    elif "ecode360.com" in amended_url:
                        scrape_html_content(amended_url, city_dir)
                    else:
                        links = scrape_links(driver, amended_url)
                        
                        # Log if we're only scraping PDFs
                        if links and all(link[0] == "pdf" for link in links):
                            log_outlier(city, amended_url)  # Log city and original URL
                        
                        for link_type, link_url in links:
                            try:
                                if link_type == "pdf":
                                    download_pdf(link_url, city_dir)
                                else:
                                    scrape_html_content(link_url, city_dir)
                            except Exception as e:
                                log_failed_url(city, link_url, str(e))
                    
                    # Mark URL as processed
                    state["processed_urls"].add(url)
                    save_state()
                    break
                    
                except ConnectionAbortedError as e:
                    logging.warning(f"Cloudflare blocked {domain}, adding to blocklist")
                    state["blocked_domains"].add(domain)
                    log_failed_url(city, amended_url, str(e))
                    state["processed_urls"].add(url)  # Mark as processed
                    save_state()
                    break
                except Exception as e:
                    retries -= 1
                    logging.warning(f"Retrying {domain} ({retries} attempts left)")
                    if driver:
                        driver.quit()
                        driver = None
                    time.sleep(random.uniform(5, 10))
            else:
                log_failed_url(city, amended_url, "Max retries exceeded")
                state["processed_urls"].add(url)  # Mark as processed
                save_state()

    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
    finally:
        if driver:
            driver.quit()
        save_state()  # Ensure state is saved on exit
        logging.info(f"Completed with {len(state['blocked_domains'])} blocked domains")

if __name__ == "__main__":
    main()
