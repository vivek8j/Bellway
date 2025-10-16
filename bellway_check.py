import requests
from bs4 import BeautifulSoup
import csv
import time
from playwright.sync_api import sync_playwright
import re
from datetime import datetime
import urllib3
import logging
import random
import signal
import sys


RUN_DATE = datetime.now().strftime('%m_%d_%Y_%H_%M_%S')
LOG_FILE = f"bellway_log_{RUN_DATE}.log"
OUTPUT_CSV = f"mpi_bellway_{RUN_DATE}.csv"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

rows = []
base_info = None  # Global variable to store base info for interrupt handler

def fn_handle_interrupt(signal, frame):
    logging.warning("Script interrupted. Saving progress...")
    if base_info:
        fn_save_csv(rows, base_info)
    else:
        logging.warning("No base info available for saving")
    sys.exit(0)

signal.signal(signal.SIGINT, fn_handle_interrupt)

def fn_human_delay(min_delay=0.5, max_delay=1.5):
    """Sleep for a random time between min_delay and max_delay seconds."""
    delay = random.uniform(min_delay, max_delay)
    time.sleep(delay)


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
}

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
BASE_URL = "https://www.bellway.co.uk"

def fn_get_base_info():
    return {
        "COMPANY_NAME": "BELLWAY", 
        "BRAND_NAME": "BELLWAY",
        "SOURCE_SITE": "BELLWAY", 
        "OUTLET": "NOT_AVAILABLE",
        "REGION": "NOT_AVAILABLE", 
        "ADDRESS": "NOT_AVAILABLE",
        "AREA": "NOT_AVAILABLE", 
        "SUB_AREA": "NOT_AVAILABLE",
        "COUNTY": "NOT_AVAILABLE", 
        "CITY":"NOT_AVAILABLE",
        "LOCATION": "NOT_AVAILABLE",
        "POSTCODE": "NOT_AVAILABLE", 
        "PLOT": "NOT_AVAILABLE",
        "TYPE": "NOT_AVAILABLE", 
        "PROPERTY_TYPE": "NOT_AVAILABLE",
        "PRICE_RANGE": "NOT_AVAILABLE", 
        "PRICE_LATEST": "NOT_AVAILABLE",
        "AVAILABILITY": "NOT_AVAILABLE", 
        "BEDROOM": "NOT_AVAILABLE",
        "BATHROOM": "NOT_AVAILABLE", 
        "LIVING_ROOM": "NOT_AVAILABLE",
        "GROUND_FLOOR_DIMENSIONS": "NOT_AVAILABLE",
        "FIRST_FLOOR_DIMENSIONS": "NOT_AVAILABLE",
        "SECOND_FLOOR_DIMENSIONS": "NOT_AVAILABLE",
        "LONGITUDE": "NOT_AVAILABLE", 
        "LATITUDE": "NOT_AVAILABLE",
        "SCHEMES_OFFERS": "NOT_AVAILABLE",
        "SCHEMES_OFFERS_DATE": "NOT_AVAILABLE",
        "EVENT": "NOT_AVAILABLE", 
        "EVENT_DATE": "NOT_AVAILABLE",
        "FEATURES": "NOT_AVAILABLE", 
        "TENURE": "NOT_AVAILABLE",
        "NHBC_WARRANTY": "NOT_AVAILABLE", 
        "HBF_STAR_RATING": "NOT_AVAILABLE",
        "PARKING_CONFIGURATION": "NOT_AVAILABLE",
        "EXPECTED_COMPLETION_DATE": "NOT_AVAILABLE",
        "PROXIMITY": "NOT_AVAILABLE", 
        "RUN_DATE": RUN_DATE,
        "URL": "NOT_AVAILABLE"
    }
    
def fn_save_csv(rows, base):
    if not rows:
        logging.warning("No data to save.")
        return
    try:
        logging.info(f"Saving {len(rows)} records to {OUTPUT_CSV}")
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(base.keys()))
            writer.writeheader()
            for r in rows:
                writer.writerow(r)
        logging.info(f"Successfully saved {len(rows)} records to {OUTPUT_CSV}")
    except Exception as e:
        logging.error(f"Error saving CSV: {e}")

def fn_fetch_page_data(url, retries=3, timeout=30):
    attempt = 0
    while attempt < retries:
        try:
            logging.info(f"Fetching URL: {url}")
            response = requests.get(url, headers=HEADERS, timeout=timeout, verify=False)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, requests.exceptions.Timeout) as e:
            attempt += 1
            logging.warning(f"Error fetching {url}: {e}. Retrying {attempt}/{retries}...")
            time.sleep(2)
    logging.error(f"Failed to fetch {url} after {retries} attempts.")
    return None


def fn_get_our_locations_url():
    fn_human_delay()
    logging.info("Fetching 'Our locations' URL...")
    resp = requests.get(BASE_URL, headers=HEADERS, verify=False)
    soup = BeautifulSoup(resp.text, 'html.parser')
    for div in soup.find_all('div', class_='nav-link with-dropdown'):
        a = div.find('a', href=True)
        if a and 'Buying with Bellway' in a.text:
            for link in div.find_all('a', class_='dropdown-nav-link'):
                span = link.find('span', class_='text')
                if span and 'Our locations' in span.text:
                    url = BASE_URL + link['href']
                    logging.info(f"Found locations page: {url}")
                    return url
    return None

def fn_scrape_map_regions(loc_url):
    """Scrape regions from the map links instead of info-boxes"""
    fn_human_delay()
    logging.info(f"Scraping map regions from {loc_url}")
    resp = requests.get(loc_url, headers=HEADERS, verify=False)
    soup = BeautifulSoup(resp.text, 'html.parser')
    regions = []
    
    # Look for map links with class 'map-point'
    map_div = soup.find('div', class_='map')
    if map_div:
        for link in map_div.find_all('a', class_='map-point', href=True):
            span = link.find('span')
            if span:
                name = span.text.strip()
                url = BASE_URL + link['href']
                regions.append({'name': name, 'url': url})
                logging.info(f"Found map region: {name} - {url}")
    
    logging.info(f"Found {len(regions)} regions from map.")
    return regions

def fn_scrape_developments_from_tiles(region_url):
    """Scrape developments from the new tile-based structure"""
    fn_human_delay()
    logging.info(f"Scraping developments from tiles: {region_url}")
    resp = requests.get(region_url, headers=HEADERS, verify=False)
    soup = BeautifulSoup(resp.text, 'html.parser')
    devs = []
    
    # Look for the search results container
    search_container = soup.find('section', class_='search-results-container')
    if not search_container:
        search_container = soup.find('div', class_='search__results')
    
    if search_container:
        # Find all tiles with development data
        tiles = search_container.find_all('div', class_='tile', attrs={'data-development-search-result': ''})
        if not tiles:
            # Fallback to any tile with class 'tile'
            tiles = search_container.find_all('div', class_='tile')
        
        logging.info(f"Found {len(tiles)} tiles to process")
        
        for tile in tiles:
            name = None
            url = None
            
            # Look for tile content section
            tile_content = tile.find('div', class_='tile__content')
            if tile_content:
                # Method 1: Extract from heading link
                heading_link = tile_content.find('a', href=True)
                if heading_link:
                    heading = heading_link.find('h4', class_='heading')
                    if heading:
                        name = heading.text.strip()
                        url = BASE_URL + heading_link['href']
                
                # Method 2: If no heading found, look for "View development" button
                if not name or not url:
                    cta_wrapper = tile_content.find('div', class_='tile__content__cta-wrapper')
                    if cta_wrapper:
                        view_link = cta_wrapper.find('a', class_='button', href=True)
                        if view_link and 'View development' in view_link.text:
                            url = BASE_URL + view_link['href']
                            # Try to get name from previous h4
                            h4 = tile_content.find('h4', class_='heading')
                            if h4:
                                name = h4.text.strip()
                            else:
                                # Extract name from URL as fallback
                                url_parts = view_link['href'].split('/')
                                name = url_parts[-1].replace('-', ' ').title() if url_parts else "Unknown Development"
                
                if name and url:
                    devs.append({'name': name, 'url': url})
                    logging.info(f"Found development: {name} - {url}")
                else:
                    logging.warning(f"Could not extract development info from tile")
    
    else:
        logging.warning(f"No search results container found on {region_url}")
    
    logging.info(f"Found {len(devs)} developments from tiles.")
    return devs

def fn_extract_postcode(address, default):
    m = re.search(r'([A-Z]{1,2}\d{1,2}[A-Z]?\s*\d[A-Z]{2})', address, re.I)
    return m.group(1).upper().strip() if m else default

def fn_extract_location_and_county(address, default_location="NOT_AVAILABLE", default_county="NOT_AVAILABLE"):
    """Extracts LOCATION as the third-to-last part and COUNTY as the second-to-last part from the address."""
    if ',' in address:
        parts = [x.strip() for x in address.split(',') if x.strip()]
        if len(parts) >= 3:
            location = parts[-3] 
            county = parts[-2]   
            return location, county
    return default_location, default_county


postcode_cache = {}

def fn_get_postcode_data(postcode):
    postcode_clean = postcode.replace(" ", "").upper()

    if not postcode_clean or postcode_clean == "NOT_AVAILABLE":
        return {
            "city": "NOT_AVAILABLE",
            "latitude": "NOT_AVAILABLE",
            "longitude": "NOT_AVAILABLE"
        }

    if postcode_clean in postcode_cache:
        return postcode_cache[postcode_clean]

    url = f"https://api.postcodes.io/postcodes/{postcode_clean}"
    try:
        resp = requests.get(url, timeout=10, verify=False)
        if resp.status_code == 200:
            data = resp.json().get("result", {})
            city = data.get("admin_district") or data.get("nuts") or "NOT_AVAILABLE"
            latitude = data.get("latitude") or "NOT_AVAILABLE"
            longitude = data.get("longitude") or "NOT_AVAILABLE"
        elif resp.status_code == 404:
            logging.info(f"Postcode not found: {postcode_clean}")
            city = latitude = longitude = "NOT_AVAILABLE"
        else:
            logging.warning(f"Unexpected status code {resp.status_code} for postcode {postcode_clean}")
            city = latitude = longitude = "NOT_AVAILABLE"
    except Exception as e:
        logging.warning(f"Could not fetch data for postcode {postcode_clean}: {e}")
        city = latitude = longitude = "NOT_AVAILABLE"

    result = {
        "city": city,
        "latitude": latitude,
        "longitude": longitude
    }

    postcode_cache[postcode_clean] = result
    return result

def fn_extract_proximity_and_parking(dev_html, base):
    soup = BeautifulSoup(dev_html, 'html.parser')
    prox = []
    parking = base["PARKING_CONFIGURATION"]
    parking_keywords = ['garage', 'driveway', 'parking', 'allocated space', 'car port', 'off-road', 'garden']

    fdiv = soup.find('div', class_='column', attrs={'data-read-more-outer': True})
    if fdiv:
        for li in fdiv.find_all('li'):
            txt = li.get_text(strip=True)
            txt_lower = txt.lower()
            if any(w in txt_lower for w in ['station','drive','minute','mile','km','near','close to','nearby']):
                prox.append(txt)
            if parking == base["PARKING_CONFIGURATION"] and any(k in txt_lower for k in parking_keywords):
                parking = txt

    return " / ".join(prox) if prox else base["PROXIMITY"], parking

def fn_scrape_development_details(dev_url, base):
    fn_human_delay()
    resp = requests.get(dev_url, headers=HEADERS, verify=False)
    soup = BeautifulSoup(resp.text, 'html.parser')
    address = base["ADDRESS"]
    price = base["PRICE_RANGE"]
    ds = soup.find('div', class_='details static')
    if ds:
        left = ds.find('div', class_='left')
        if left:
            spans = left.find_all('span')
            if spans:
                address = spans[0].text.strip()
                if len(spans) > 1:
                    price = spans[1].text.strip()
    postcode = fn_extract_postcode(address, base["POSTCODE"])

    # Extract LOCATION and COUNTY from the address
    loc, county = fn_extract_location_and_county(address)
    base["LOCATION"] = loc
    base["COUNTY"] = county

    postcode_data = fn_get_postcode_data(postcode)
    
    base["CITY"] = postcode_data["city"]
    base["LATITUDE"] = postcode_data["latitude"]
    base["LONGITUDE"] = postcode_data["longitude"]

    types = []
    rd = soup.find('div', class_='results')
    if rd:
        for art in rd.find_all('article', class_='slick-slide'):
            ts = art.find('span', class_='result-title')
            link = art.find('a', class_='button', href=True)
            if ts and link:
                types.append({'name': ts.text.strip(), 'url': BASE_URL + link['href']})
    return address, postcode, loc, price, types

def fn_extract_floor_dimensions(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    blocks = soup.select('div.carousel-text-container > div.content > div.content')
    keys = ["GROUND_FLOOR_DIMENSIONS","FIRST_FLOOR_DIMENSIONS","SECOND_FLOOR_DIMENSIONS"]
    dims = {k: [base[k]] for k in keys}

    for idx, block in enumerate(blocks):
        if idx >= len(keys): 
            break
        entries = block.find_all(['h3','p'])
        lines = []
        count = 1
        for i in range(0, len(entries), 2):
            if i + 1 < len(entries):
                lbl = entries[i].get_text(strip=True).rstrip(':')
                val = entries[i + 1].get_text(strip=True)
                lines.append(f"{count}. {lbl}: {val}")
                count += 1
        if lines:
            dims[keys[idx]] = lines
    return dims

def fn_count_rooms(dims):
    b = ba = l = 0
    for lines in dims.values():
        for ln in lines:
            lw = ln.lower()

            # Bedroom: exclude "en suite" or similar additions
            if 'bedroom' in lw and not any(x in lw for x in ['en suite', 'ensuite']):
                b += 1

            # Bathroom
            elif 'bathroom' in lw:
                ba += 1

            # Living / common areas
            elif any(x in lw for x in ['living', 'dining', 'lounge', 'reception']):
                l += 1

    return b, ba, l


def fn_scrape_type_page(playwright, type_url, type_name, base):
    browser = None
    page = None
    try:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(type_url, timeout=60000)
        page.wait_for_selector('div.column[data-read-more-outer]', timeout=10000, state="attached")
    except Exception as e:
        logging.error(f"Failed to load or render {type_url}: {e}")
        if browser:
            try:
                browser.close()
            except Exception as close_err:
                logging.warning(f"Error closing browser after failed load: {close_err}")
        return base["FEATURES"], base["NHBC_WARRANTY"], {}, base["BEDROOM"], base["BATHROOM"], base["LIVING_ROOM"], []

    try:
        html_type = page.content()
        soup = BeautifulSoup(html_type, 'html.parser')
        
        # First, extract the actual TYPE name from the page title
        actual_type_name = type_name
        title_h1 = soup.select_one('main.house-development h1')
        if title_h1:
            actual_type_name = title_h1.get_text(strip=True)
            logging.info(f"Found page TYPE name: {actual_type_name}")
        
        # Convert type name to data-house-style format (e.g., "The Kinloch" -> "the-kinloch")
        style_slug = actual_type_name.lower().replace(" ", "-")
        logging.info(f"Looking for plots with style slug: {style_slug}")

        features = []
        fdiv = soup.find('div', class_='column', attrs={'data-read-more-outer': True})
        if fdiv:
            for li in fdiv.find_all('li'):
                txt = li.get_text(strip=True)
                if txt and txt not in features:
                    features.append(txt)
            templates = fdiv.find_all('template', attrs={'x-if': 'showMoreFeatures'})
            for tmpl in templates:
                tsoup = BeautifulSoup(tmpl.decode_contents(), 'html.parser')
                for li in tsoup.find_all('li'):
                    txt = li.get_text(strip=True)
                    if txt and txt not in features:
                        features.append(txt)

        feat_str = " / ".join(features) if features else "NOT_AVAILABLE"
        nhbc = next((f for f in features if 'nhbc' in f.lower() or 'warranty' in f.lower()), "NOT_AVAILABLE")

        dims = fn_extract_floor_dimensions(html_type, base)
        b, ba, l = fn_count_rooms(dims)
        bd = f"{b} Bedroom" if b else "NOT_AVAILABLE"
        ab = f"{ba} Bathroom" if ba else "NOT_AVAILABLE"
        lr = f"{l} Living Room" if l else "NOT_AVAILABLE"

        plots = []
        try:
            page.wait_for_selector('table.plots', timeout=10000, state="attached")
            html_plot = page.content()
            soup_plot = BeautifulSoup(html_plot, 'html.parser')
            
            # Find all plot rows in the tables
            for row in soup_plot.select('table.plots tr.plot-row'):
                # Get the house style from the data attribute
                style = row.get('data-house-style', '').strip()
                
                # Only include rows matching the current type_name (style slug)
                if style.lower() != style_slug.lower():
                    continue
                
                try:
                    # Extract plot number (first column) - e.g., "Plot 44"
                    plot_cell = row.select_one('td:nth-child(1) span')
                    num = plot_cell.get_text(strip=True) if plot_cell else "NOT_AVAILABLE"
                    num = num if num and num != "" else "NOT_AVAILABLE"
                    
                    # Extract house type (second column) - e.g., "Mid Terrace"
                    type_cell = row.select_one('td:nth-child(2) span')
                    typ = type_cell.get_text(strip=True) if type_cell else "NOT_AVAILABLE"
                    typ = typ if typ and typ != "" else "NOT_AVAILABLE"
                    
                    # Extract price (third column) - e.g., "£289,995" or "Awaiting release"
                    price_cell = row.select_one('td:nth-child(3) .table-text-container span')
                    pri = price_cell.get_text(strip=True) if price_cell else "NOT_AVAILABLE"
                    pri = pri if pri and pri != "" else "NOT_AVAILABLE"
                    
                    # Determine availability based on price
                    if pri == "NOT_AVAILABLE" or 'awaiting release' in pri.lower():
                        avail = 'Not Released'
                    elif pri.startswith('£') or pri[0].isdigit():
                        avail = 'For Sale'
                    else:
                        avail = 'Not Released'
                    
                    if num != "NOT_AVAILABLE":
                        plots.append({
                            "PLOT": num, 
                            "PROPERTY_TYPE": typ, 
                            "PRICE_LATEST": pri, 
                            "AVAILABILITY": avail
                        })
                        logging.info(f"Found plot: {num} - {typ} - {pri} - {avail}")
                except Exception as parse_err:
                    logging.warning(f"Error parsing individual plot row: {parse_err}")
                    continue
                    
        except Exception as e:
            logging.warning(f"Could not parse plots for {type_url}: {e}")

        return feat_str, nhbc, dims, bd, ab, lr, plots

    except Exception as e:
        logging.error(f"Error processing {type_url}: {e}")
        return "NOT_AVAILABLE", "NOT_AVAILABLE", {}, "NOT_AVAILABLE", "NOT_AVAILABLE", "NOT_AVAILABLE", []
    
    finally:
        if browser:
            try:
                browser.close()
            except Exception as e:
                logging.warning(f"Error closing browser: {e}")


def main():
    global base_info
    logging.info("=== Starting Bellway Scraper ===")
    base = fn_get_base_info()
    base_info = base

    # Ensure location URL is retrieved
    loc = fn_get_our_locations_url()
    if not loc:
        logging.error("Cannot find locations URL")
        return

    with sync_playwright() as p:
        try:
            # Use the new map-based region scraping
            regions = fn_scrape_map_regions(loc)
            logging.info(f"Found {len(regions)} regions from map.")
            
            for reg in regions:
                logging.info(f"Scraping region: {reg['name']}")
                # Use the new tile-based development scraping
                devs = fn_scrape_developments_from_tiles(reg['url'])
                logging.info(f"  Found {len(devs)} developments in region: {reg['name']}")

                for dev in devs:
                    logging.info(f"  Scraping development: {dev['name']} - {dev['url']}")
                    resp = fn_fetch_page_data(dev['url'])
                    if resp:
                        proximity, parking = fn_extract_proximity_and_parking(resp.text, base)

                        addr, pc, locn, price_range, types = fn_scrape_development_details(dev['url'], base)
                        logging.info(f"    Found {len(types)} property types in development.")

                        for tp in types:
                            logging.info(f"    Scraping house type: {tp['name']} - {tp['url']}")
                            feat, nhbc, dims, bd, ba, lr, plots = fn_scrape_type_page(p, tp['url'], tp['name'], base)

                            # Prepare dimensions for saving
                            ground_dims = dims.get("GROUND_FLOOR_DIMENSIONS", [])
                            first_dims = dims.get("FIRST_FLOOR_DIMENSIONS", [])
                            second_dims = dims.get("SECOND_FLOOR_DIMENSIONS", [])
                            
                            # Filter out "NOT_AVAILABLE" and join remaining dimensions
                            # ground_dim_str = "\n".join([d for d in ground_dims if d and d != "NOT_AVAILABLE"]) if ground_dims else ""
                            # first_dim_str = "\n".join([d for d in first_dims if d and d != "NOT_AVAILABLE"]) if first_dims else ""
                            # second_dim_str = "\n".join([d for d in second_dims if d and d != "NOT_AVAILABLE"]) if second_dims else ""
                            ground_dim_str = "\n".join([d for d in ground_dims if d and d != "NOT_AVAILABLE"]) or "NOT_AVAILABLE"
                            first_dim_str = "\n".join([d for d in first_dims if d and d != "NOT_AVAILABLE"]) or "NOT_AVAILABLE"
                            second_dim_str = "\n".join([d for d in second_dims if d and d != "NOT_AVAILABLE"]) or "NOT_AVAILABLE"

                            if plots:
                                for pl in plots:
                                    entry = base.copy()
                                    entry.update({
                                        "OUTLET": dev['name'], 
                                        "REGION": reg['name'],
                                        "ADDRESS": addr, 
                                        "LOCATION": locn, 
                                        "POSTCODE": pc,
                                        "COUNTY": base["COUNTY"],
                                        "CITY": base["CITY"],
                                        "TYPE": tp['name'], 
                                        "PROPERTY_TYPE": pl["PROPERTY_TYPE"],
                                        "PLOT": pl["PLOT"],
                                        "PRICE_RANGE": price_range, 
                                        "PRICE_LATEST": pl["PRICE_LATEST"],
                                        "AVAILABILITY": pl["AVAILABILITY"], 
                                        "FEATURES": feat,
                                        "PROXIMITY": proximity, 
                                        "PARKING_CONFIGURATION": parking,
                                        "GROUND_FLOOR_DIMENSIONS": ground_dim_str,
                                        "FIRST_FLOOR_DIMENSIONS": first_dim_str,
                                        "SECOND_FLOOR_DIMENSIONS": second_dim_str,
                                        "BEDROOM": bd, 
                                        "BATHROOM": ba, 
                                        "LIVING_ROOM": lr,
                                        "NHBC_WARRANTY": nhbc, 
                                        "LONGITUDE": base["LONGITUDE"],
                                        "LATITUDE": base["LATITUDE"],
                                        "URL": tp['url']
                                    })
                                    rows.append(entry)
                            else:
                                entry = base.copy()
                                entry.update({
                                    "OUTLET": dev['name'], 
                                    "REGION": reg['name'],
                                    "ADDRESS": addr, 
                                    "LOCATION": locn, 
                                    "POSTCODE": pc,
                                    "COUNTY": base["COUNTY"], 
                                    "CITY": base["CITY"],
                                    "TYPE": tp['name'],
                                    "PROPERTY_TYPE": tp['name'],
                                    "PLOT": "NO_PLOTS", 
                                    "PRICE_RANGE": price_range, 
                                    "PRICE_LATEST": "Awaiting release",
                                    "AVAILABILITY": "Not Released", 
                                    "FEATURES": feat,
                                    "PROXIMITY": proximity, 
                                    "PARKING_CONFIGURATION": parking,
                                    "GROUND_FLOOR_DIMENSIONS": ground_dim_str, 
                                    "FIRST_FLOOR_DIMENSIONS": first_dim_str,
                                    "SECOND_FLOOR_DIMENSIONS": second_dim_str,
                                    "BEDROOM": bd, 
                                    "BATHROOM": ba, 
                                    "LIVING_ROOM": lr,
                                    "NHBC_WARRANTY": nhbc, 
                                    "LONGITUDE": base["LONGITUDE"],
                                    "LATITUDE": base["LATITUDE"],
                                    "URL": tp['url']
                                })
                                rows.append(entry)
                    
                    # Save progress every 100 records
                    if len(rows) % 100 == 0:
                        fn_save_csv(rows, base)

            logging.info("Scraping completed successfully.")
        except KeyboardInterrupt:
            logging.warning("Script interrupted by user")
            fn_save_csv(rows, base)
        except Exception as e:
            logging.error(f"An error occurred: {e}")
            fn_save_csv(rows, base)
        finally:
            fn_save_csv(rows, base)

if __name__ == "__main__":
    main()