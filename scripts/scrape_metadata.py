"""Scrape Amazon product metadata for ASINs missing from McAuley dataset.

Only scrapes products with 20+ reviews that don't have metadata.
Rate-limited to be respectful. Saves results as JSON for Snowflake upload.
"""

import re
import json
import time
import random
import requests
import os

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def scrape_product(asin: str) -> dict | None:
    """Scrape a single Amazon product page."""
    url = f'https://www.amazon.com/dp/{asin}'
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        if resp.status_code != 200 or 'captcha' in resp.text.lower():
            return None

        html = resp.text
        result = {'asin': asin}

        # Title
        title_match = re.search(r'id="productTitle"[^>]*>(.*?)</span>', html, re.DOTALL)
        if title_match:
            result['title'] = title_match.group(1).strip()

        # Brand
        brand_match = re.search(r'id="bylineInfo"[^>]*>.*?>(.*?)</a>', html, re.DOTALL)
        if brand_match:
            brand = brand_match.group(1).strip()
            brand = re.sub(r'^(Visit the |Brand: )', '', brand).strip()
            brand = re.sub(r' Store$', '', brand).strip()
            result['brand'] = brand

        # Price
        price_match = re.search(r'class="a-price-whole">([\d,]+)</span>', html)
        if price_match:
            frac_match = re.search(r'class="a-price-fraction">(\d+)</span>', html)
            frac = frac_match.group(1) if frac_match else '00'
            result['price'] = f"${price_match.group(1)}.{frac}"

        # Features (bullet points)
        features = re.findall(r'<span class="a-list-item">\s*(.*?)\s*</span>', html)
        features = [f.strip() for f in features if len(f.strip()) > 10 and '<' not in f][:10]
        if features:
            result['feature'] = features

        # Category breadcrumb
        cats = re.findall(r'class="a-link-normal a-color-tertiary"[^>]*>\s*(.*?)\s*</a>', html)
        if cats:
            result['category'] = [c.strip() for c in cats if c.strip()]

        return result if 'title' in result else None

    except Exception as e:
        print(f'  Error scraping {asin}: {e}')
        return None


def main():
    # Read ASINs to scrape
    with open('data/asins_to_scrape.txt') as f:
        asins = [line.strip() for line in f if line.strip()]

    print(f'Scraping {len(asins)} ASINs...')

    results = []
    blocked = 0
    success = 0

    for i, asin in enumerate(asins):
        print(f'[{i+1}/{len(asins)}] {asin}...', end=' ')

        data = scrape_product(asin)
        if data:
            results.append(data)
            success += 1
            print(f"OK: {data.get('title', '?')[:50]}")
        else:
            blocked += 1
            print('BLOCKED/FAILED')

        # Stop if getting blocked too much
        if blocked > 10 and blocked > success:
            print(f'\nToo many blocks ({blocked}). Stopping.')
            break

        # Rate limit: 2-4 seconds between requests
        time.sleep(random.uniform(2, 4))

    # Save results
    output_path = 'data/scraped_metadata.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + '\n')

    print(f'\nDone. {success} scraped, {blocked} failed.')
    print(f'Saved to {output_path}')


if __name__ == '__main__':
    main()
