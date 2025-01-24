# 311iiiiiiiiiiiiiiiiiiiiiiiiiIIIIIIIIIIIIIIIIIIIII111111111111IIIIIIIIIIIIII111111
Scrape municipal codes and more from government websites with ease

This Python script (3ii.py) is a web scraper designed to  download and save content (HTML pages and PDF files) from a list of URLs provided in a CSV file. It was created for scraping municipal codes and bylaws off of city and town government websites. 

Useful for journalists, researchers, architects, and anyone who has a list of urls they need to scrape for containing a mix of html and pdf files. 

This was specifically created to be able to automatically download Massachusetts municipal codes, after I learned there was no convenient way to search across all city and town bylaws. There are paid services available, but these are not exhaustive databases. I used a list of links from mass.gov available [here](https://www.mass.gov/info-details/massachusetts-city-and-town-ordinances-and-by-laws). 

Some of this readme was AI generated so it might read a little weird as I fill in some of the details in my less affable voice. Got it! Okay! Now here's what the Web Scraper for Municipal Codes and Documents does!
## Features

- **Pause/Resume Functionality**: The script can save its progress and resume from where it left off if interrupted. Use Ctrl + C to quit and it will pause automatically. 
- **Sneaky anti-bot detection stuff.
- **Rate Limiting**: Introduces random delays between requests to avoid triggering rate limits or bans.
- **User Agent Rotation**: Periodically changes the user agent to mimic different browsers and reduce the chance of being blocked.
- **Error Handling**: Logs failed URLs and retries them a specified number of times before giving up.
- **State Management**: Maintains a state file (`scraper_state.json`) to track progress, blocked domains, and processed URLs.

## Requirements

- Python 3.7 or higher
- Required Python packages (install via `pip install -r requirements.txt`):
  ```plaintext
  selenium
  undetected-chromedriver
  beautifulsoup4
  html2text
  fake_useragent
  requests
  ```

## Installation

You can just download 3ii.py and run it in a directory that contains a file named urls.csv that follows the format below, or you can do the following: 

1. Clone the repository:
   ```bash
   git clone https://github.com/JonGerhardson/311iiiiiiiiiiiiiiiiiiiiiiiiiIIIIIIIIIIIIIIIIIIIII111111111111IIIIIIIIIIIIII111111.git
   cd 311iiiiiiiiiiiiiiiiiiiiiiiiiIIIIIIIIIIIIIIIIIIIII111111111111IIIIIIIIIIIIII111111
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Prepare a CSV file (`urls.csv`) with the URLs to scrape. Each row should have two columns:
   - **City**: A name or identifier for the URL (e.g., "Boston").
   - **URL**: The web address to scrape.

   Example `urls.csv`:
   ```csv
   City,URL
   Boston,https://example.com/boston
   New York,https://example.com/newyork
   Chicago,https://example.com/chicago
   ```

## Usage

1. Run the script:
   ```bash
   python 3ii.py
   ```

2. To pause the script:
   - Press `Ctrl+C`. The script will save its progress and exit gracefully.

3. To resume the script:
   - Run the script again. It will load the saved state and continue from where it left off.
4. If you need to start over from the beginning, delete 'scraper.state.json.'

## Output

- **Downloaded Content**:
  - The downloaded content is saved in a directory structure under `downloaded_content/`.
  - Subdirectories are created for each city (based on the CSV input).
  - HTML content is saved as Markdown files (`.md`).
  - PDF files are downloaded directly.

- **Log Files**:
  - `scraper.log`: Contains detailed logs of the script's execution.
  - `outliers.csv`: Logs URLs that only contain PDF links. (This is from when I was troubleshooting and you can probably just ignore it.)
  - `failed_urls.csv`: Logs URLs that failed to process, along with the error message.
    Either of these CSV files can be renamed to 'urls.csv' and you can run the script again if needed. Just be sure to delete scraper.state.json and make a backup of your original urls.csv beforehand. 

- **State File**:
  - `scraper_state.json`: Tracks the script's progress, including processed URLs, blocked domains, and the current index.

## Example Workflow

1. **Input (`urls.csv`)**:
   ```csv
   City,URL
   Boston,https://example.com/boston
   New York,https://example.com/newyork
   Chicago,https://example.com/chicago
   ```

2. **Output**:
   - **Directory Structure**:
     ```
     downloaded_content/
     ├── Boston/
     │   └── boston_code.txt
     ├── New York/
     │   ├── page1.md
     │   └── document.pdf
     └── Chicago/
         └── page2.md
     ```
   - **Log Files**:
     - `outliers.csv`: Logs URLs with only PDF links.
     - `failed_urls.csv`: Logs URLs that failed to process.

3. **State File (`scraper_state.json`)**:
   ```json
   {
     "processed_urls": ["https://example.com/boston", "https://example.com/newyork"],
     "blocked_domains": ["example.com"],
     "current_index": 2
   }
   ```

## Limitations

- **Municode.com** sites do not currently work. For Massachusetts there's only a handful of cities using this service so it is easier for me to just grab those manually than figure out a workaround. Reach out if you have a good way to handle these sites. 

- **Civic Plus** websites seem to be more sensitive to bots than others and you might need to retry them a couple times. 

- **ecode360.com** rather than trying to slog through all of the javascript the script uses a trick to amend the url to the plain html one you get when you click print all. 
  For example: https://ecode360.com/AD2021 
  becomes: https://ecode360.com/print/AD2021?guid=AD2021 
   This might not always work for every ecode360.com link, but it's worked for every one I've tried. 

-  If you have an entry in urls.csv labled Boston, this script will ignore that url and instead print the lyrics to "[This is Boston, Not L.A](https://youtu.be/zt-C7ZTFxbQ?si=RY4qlBbnHjZDZcaz)," by The Freeze. 
## License

Free for commercial and non-commercial use, except that you may not use this script to create a database of government documents  or public domain information as-a-service for paid subscribers. You can do that if it can be freely accessed by anyone without paying or creating a user account. You can use this for any other commercial purpose. You must license any derivative works using this same license. You can't sue me and have to be nice to me.  

---

