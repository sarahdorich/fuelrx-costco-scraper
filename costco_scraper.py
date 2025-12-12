"""
Costco Inventory Scraper for FuelRx
Scrapes Costco.com inventory for Sandy, UT warehouse and stores in Supabase
"""

import os
import re
import time
from datetime import datetime
from typing import List, Dict, Optional
from supabase import create_client, Client
from playwright.sync_api import sync_playwright, Page, Browser

# Configuration
WAREHOUSE_ADDRESS = "11100 S AUTO MALL DR Sandy, UT 84070-4171"
WAREHOUSE_ZIP = "84070"

# Categories to scrape
CATEGORIES = {
    "meat_seafood": "https://www.costco.com/meat.html",
    "deli": "https://www.costco.com/deli.html",
    "prepared_meals": "https://www.costco.com/prepared-food.html",
    "pantry": "https://www.costco.com/pantry.html",
    "organic": "https://www.costco.com/organic-groceries.html",
    "cheese_dairy": "https://www.costco.com/dairy-eggs-cheese.html",
    "snacks": "https://www.costco.com/snacks.html",
    "mixt_pantry": "https://costconext.com/brand/mixt-pantry/",
}

class CostcoScraper:
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize scraper with Supabase connection"""
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.warehouse_set = False
        
    def set_warehouse(self, page: Page, zip_code: str) -> bool:
        """Set the warehouse location on Costco.com"""
        try:
            print(f"Setting warehouse to zip code: {zip_code}")
            
            # Look for warehouse/location selector
            # Costco typically has a "Set Your Warehouse" link or button
            warehouse_button = page.locator("text=/Set Your Warehouse|Change Warehouse|Warehouse/i").first
            
            if warehouse_button.is_visible(timeout=5000):
                warehouse_button.click()
                time.sleep(2)
                
                # Enter zip code
                zip_input = page.locator("input[placeholder*='ZIP' i], input[name*='zip' i], input[id*='zip' i]").first
                if zip_input.is_visible(timeout=5000):
                    zip_input.fill(zip_code)
                    time.sleep(1)
                    
                    # Submit
                    submit_btn = page.locator("button:has-text('Search'), button:has-text('Find'), button[type='submit']").first
                    if submit_btn.is_visible(timeout=3000):
                        submit_btn.click()
                        time.sleep(3)
                        
                        # Select the Sandy warehouse from results
                        warehouse_option = page.locator(f"text=/{zip_code}/i").first
                        if warehouse_option.is_visible(timeout=5000):
                            warehouse_option.click()
                            time.sleep(2)
                            self.warehouse_set = True
                            print("✓ Warehouse set successfully")
                            return True
            
            print("⚠ Could not find warehouse selector - continuing anyway")
            return True  # Continue even if we can't set warehouse
            
        except Exception as e:
            print(f"⚠ Error setting warehouse: {e}")
            return True  # Continue anyway
    
    def extract_price(self, text: str) -> Optional[float]:
        """Extract price from text"""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+\.?\d*)', text.replace(',', ''))
        return float(match.group(1)) if match else None
    
    def scrape_product_card(self, product_element, category: str) -> Optional[Dict]:
        """Extract product data from a product card element"""
        try:
            product = {
                'category': category,
                'warehouse_location': 'Sandy, UT',
                'last_scraped_at': datetime.utcnow().isoformat(),
            }
            
            # Product name
            name_elem = product_element.locator(".description, .product-title, h3, a.product-link").first
            if name_elem.is_visible(timeout=1000):
                product['name'] = name_elem.inner_text().strip()
            else:
                return None  # Skip if no name
            
            # Price
            price_elem = product_element.locator(".price, .product-price, [class*='price']").first
            if price_elem.is_visible(timeout=1000):
                price_text = price_elem.inner_text().strip()
                product['price'] = self.extract_price(price_text)
            
            # Image
            img_elem = product_element.locator("img").first
            if img_elem.is_visible(timeout=1000):
                product['image_url'] = img_elem.get_attribute("src") or img_elem.get_attribute("data-src")
            
            # Product URL
            link_elem = product_element.locator("a[href*='product']").first
            if link_elem.is_visible(timeout=1000):
                product['product_url'] = link_elem.get_attribute("href")
                if product['product_url'] and not product['product_url'].startswith('http'):
                    product['product_url'] = f"https://www.costco.com{product['product_url']}"
            
            # Brand (if available)
            brand_elem = product_element.locator(".brand, [class*='brand']").first
            if brand_elem.is_visible(timeout=1000):
                product['brand'] = brand_elem.inner_text().strip()
            
            return product if product.get('name') else None
            
        except Exception as e:
            print(f"  ⚠ Error extracting product: {e}")
            return None
    
    def scrape_category(self, page: Page, category_name: str, url: str) -> List[Dict]:
        """Scrape all products from a category page"""
        print(f"\n{'='*60}")
        print(f"Scraping: {category_name}")
        print(f"URL: {url}")
        print(f"{'='*60}")
        
        products = []
        
        try:
            # Navigate to category page
            page.goto(url, wait_until="networkidle", timeout=30000)
            time.sleep(3)  # Wait for dynamic content
            
            # Scroll to load lazy-loaded products
            print("Scrolling to load all products...")
            for _ in range(5):  # Scroll 5 times
                page.evaluate("window.scrollBy(0, 1000)")
                time.sleep(1)
            
            # Find all product cards - adjust selectors based on Costco's actual HTML
            product_selectors = [
                ".product-tile",
                ".product-item",
                ".product",
                "[class*='product-']",
                ".automation-id-tile"
            ]
            
            product_cards = None
            for selector in product_selectors:
                try:
                    product_cards = page.locator(selector).all()
                    if len(product_cards) > 0:
                        print(f"Found {len(product_cards)} products using selector: {selector}")
                        break
                except:
                    continue
            
            if not product_cards or len(product_cards) == 0:
                print(f"⚠ No products found on {category_name}")
                return products
            
            # Extract data from each product card
            for i, card in enumerate(product_cards, 1):
                try:
                    product = self.scrape_product_card(card, category_name)
                    if product:
                        products.append(product)
                        print(f"  [{i}/{len(product_cards)}] ✓ {product['name'][:50]}...")
                    else:
                        print(f"  [{i}/{len(product_cards)}] ✗ Skipped (invalid data)")
                        
                except Exception as e:
                    print(f"  [{i}/{len(product_cards)}] ✗ Error: {e}")
                    continue
            
            print(f"\n✓ Successfully scraped {len(products)} products from {category_name}")
            
        except Exception as e:
            print(f"✗ Error scraping category {category_name}: {e}")
        
        return products
    
    def save_to_database(self, products: List[Dict]) -> int:
        """Save products to Supabase database"""
        if not products:
            return 0
        
        print(f"\nSaving {len(products)} products to database...")
        saved_count = 0
        
        for product in products:
            try:
                # Upsert based on product_url to avoid duplicates
                result = self.supabase.table('costco_products').upsert(
                    product,
                    on_conflict='product_url'
                ).execute()
                saved_count += 1
                
            except Exception as e:
                print(f"  ✗ Error saving product '{product.get('name', 'Unknown')}': {e}")
                continue
        
        print(f"✓ Successfully saved {saved_count}/{len(products)} products")
        return saved_count
    
    def run(self):
        """Main scraping workflow"""
        print("="*60)
        print("COSTCO INVENTORY SCRAPER FOR FUELRX")
        print("="*60)
        print(f"Target warehouse: {WAREHOUSE_ADDRESS}")
        print(f"Categories to scrape: {len(CATEGORIES)}")
        print("="*60)
        
        all_products = []
        
        with sync_playwright() as p:
            # Launch browser (use headless=False to see what's happening)
            print("\nLaunching browser...")
            browser: Browser = p.chromium.launch(headless=False)  # Set to True for production
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            # Set warehouse location
            page.goto("https://www.costco.com", wait_until="networkidle")
            time.sleep(3)
            self.set_warehouse(page, WAREHOUSE_ZIP)
            
            # Scrape each category
            for category_name, url in CATEGORIES.items():
                try:
                    products = self.scrape_category(page, category_name, url)
                    all_products.extend(products)
                    
                    # Save batch to database after each category
                    if products:
                        self.save_to_database(products)
                    
                    # Be nice to the server
                    time.sleep(2)
                    
                except Exception as e:
                    print(f"✗ Failed to scrape {category_name}: {e}")
                    continue
            
            browser.close()
        
        # Final summary
        print("\n" + "="*60)
        print("SCRAPING COMPLETE")
        print("="*60)
        print(f"Total products scraped: {len(all_products)}")
        print(f"Categories processed: {len(CATEGORIES)}")
        print("="*60)

def main():
    """Entry point"""
    # Get environment variables
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # Use service role key for admin access
    
    if not supabase_url or not supabase_key:
        print("ERROR: Missing environment variables!")
        print("Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        print("\nExample:")
        print("export SUPABASE_URL='https://your-project.supabase.co'")
        print("export SUPABASE_SERVICE_ROLE_KEY='your-service-role-key'")
        return
    
    # Run scraper
    scraper = CostcoScraper(supabase_url, supabase_key)
    scraper.run()

if __name__ == "__main__":
    main()
    