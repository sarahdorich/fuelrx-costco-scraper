"""
Costco Inventory Scraper for FuelRx
Scrapes Costco.com inventory for Sandy, UT warehouse and stores in Supabase
Uses undetected-chromedriver to bypass bot detection
"""

import os
import random
import re
import time
from datetime import datetime
from typing import List, Dict, Optional
from supabase import create_client, Client
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

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
}

# Whether to scrape individual product pages for detailed info (slower but more data)
SCRAPE_PRODUCT_DETAILS = True

# Run in headless mode (set to False if you need to debug)
HEADLESS = False


class CostcoScraper:
    def __init__(self, supabase_url: str, supabase_key: str):
        """Initialize scraper with Supabase connection"""
        self.supabase: Client = create_client(supabase_url, supabase_key)
        self.warehouse_set = False
        self.driver = None

    def create_driver(self):
        """Create an undetected Chrome driver"""
        options = uc.ChromeOptions()

        # Set window size
        options.add_argument("--window-size=1920,1080")

        # Set locale and timezone
        options.add_argument("--lang=en-US")

        # Disable automation flags
        options.add_argument("--disable-blink-features=AutomationControlled")

        if HEADLESS:
            options.add_argument("--headless=new")

        # Create the undetected driver
        driver = uc.Chrome(options=options, version_main=None)

        # Set page load timeout
        driver.set_page_load_timeout(60)

        return driver

    def set_warehouse(self, zip_code: str) -> bool:
        """Set the warehouse location on Costco.com"""
        try:
            print(f"Setting warehouse to zip code: {zip_code}")

            # Look for warehouse/location selector using various approaches
            warehouse_selectors = [
                "//button[contains(text(), 'Set Your Warehouse')]",
                "//a[contains(text(), 'Set Your Warehouse')]",
                "//button[contains(text(), 'Change Warehouse')]",
                "//a[contains(text(), 'Change Warehouse')]",
                "//*[contains(@class, 'warehouse') and contains(@class, 'select')]",
                "//button[@id='warehouse-set-498']",
            ]

            warehouse_button = None
            for selector in warehouse_selectors:
                try:
                    warehouse_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    break
                except TimeoutException:
                    continue

            if warehouse_button:
                warehouse_button.click()
                time.sleep(2)

                # Enter zip code
                zip_selectors = [
                    "//input[contains(@placeholder, 'ZIP')]",
                    "//input[contains(@name, 'zip')]",
                    "//input[contains(@id, 'zip')]",
                    "//input[@type='text' and ancestor::*[contains(@class, 'warehouse')]]",
                ]

                zip_input = None
                for selector in zip_selectors:
                    try:
                        zip_input = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, selector))
                        )
                        break
                    except TimeoutException:
                        continue

                if zip_input:
                    zip_input.clear()
                    zip_input.send_keys(zip_code)
                    time.sleep(1)

                    # Submit
                    submit_selectors = [
                        "//button[contains(text(), 'Search')]",
                        "//button[contains(text(), 'Find')]",
                        "//button[@type='submit']",
                        "//input[@type='submit']",
                    ]

                    for selector in submit_selectors:
                        try:
                            submit_btn = self.driver.find_element(By.XPATH, selector)
                            if submit_btn.is_displayed():
                                submit_btn.click()
                                time.sleep(3)
                                break
                        except NoSuchElementException:
                            continue

                    # Select warehouse from results
                    try:
                        warehouse_option = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, f"//*[contains(text(), '{zip_code}')]"))
                        )
                        warehouse_option.click()
                        time.sleep(2)
                        self.warehouse_set = True
                        print("Warehouse set successfully")
                        return True
                    except TimeoutException:
                        pass

            print("Could not find warehouse selector - continuing anyway")
            return True

        except Exception as e:
            print(f"Error setting warehouse: {e}")
            return True

    def extract_price(self, text: str) -> Optional[float]:
        """Extract price from text"""
        if not text:
            return None
        match = re.search(r'\$?([\d,]+\.?\d*)', text.replace(',', ''))
        return float(match.group(1)) if match else None

    def extract_number(self, text: str) -> Optional[int]:
        """Extract a number from text (for nutritional values)"""
        if not text:
            return None
        match = re.search(r'(\d+)', text)
        return int(match.group(1)) if match else None

    def scrape_product_card(self, product_element, category: str) -> Optional[Dict]:
        """Extract product data from a product card element"""
        try:
            product = {
                'category': category,
                'warehouse_location': 'Sandy, UT',
                'last_scraped_at': datetime.utcnow().isoformat(),
            }

            # Try to get product ID from the tile's data-testid attribute
            try:
                testid = product_element.get_attribute("data-testid")
                if testid and testid.startswith("ProductTile_"):
                    product['costco_id'] = testid.replace("ProductTile_", "")
            except:
                pass

            # Product name - try new MUI selectors first, then legacy
            name_selectors = [
                # New MUI-based selectors (data-testid contains title)
                (By.CSS_SELECTOR, "[data-testid*='_title']"),
                (By.CSS_SELECTOR, "[data-testid^='Text_ProductTile_']"),
                # Link text as fallback
                (By.CSS_SELECTOR, "[data-testid='Link'] span"),
                (By.CSS_SELECTOR, "a[href*='.html'] span"),
                # Legacy selectors
                (By.XPATH, ".//span[contains(@class, 'description')]//a"),
                (By.XPATH, ".//a[contains(@class, 'description')]"),
                (By.XPATH, ".//*[contains(@class, 'product-title')]//a"),
                (By.XPATH, ".//a[@automation-id='productDescriptionLink']"),
                (By.XPATH, ".//*[contains(@class, 'product-description')]//a"),
                (By.XPATH, ".//h3//a"),
                (By.XPATH, ".//a[contains(@href, '/p/')]"),
            ]

            name_found = False
            for by, selector in name_selectors:
                try:
                    name_elem = product_element.find_element(by, selector)
                    name_text = name_elem.text.strip()
                    if name_text and len(name_text) > 3:
                        product['name'] = name_text
                        name_found = True
                        break
                except NoSuchElementException:
                    continue

            if not name_found:
                return None

            # Price - try new MUI selectors first
            price_selectors = [
                # New MUI-based selectors
                (By.CSS_SELECTOR, "[data-testid^='Text_Price_']"),
                (By.CSS_SELECTOR, "[data-testid^='PriceGroup_'] [data-testid='Text']"),
                # Legacy selectors
                (By.XPATH, ".//*[contains(@class, 'price')]"),
                (By.XPATH, ".//*[@automation-id='itemPriceOutput']"),
                (By.XPATH, ".//*[contains(@class, 'your-price')]//*[contains(@class, 'value')]"),
                (By.XPATH, ".//*[contains(@class, 'item-price')]"),
            ]

            for by, selector in price_selectors:
                try:
                    price_elem = product_element.find_element(by, selector)
                    price_text = price_elem.text.strip()
                    if price_text:
                        product['price'] = self.extract_price(price_text)
                        if product['price']:
                            break
                except NoSuchElementException:
                    continue

            # Image - try new MUI selector first
            image_selectors = [
                (By.CSS_SELECTOR, "[data-testid^='ProductImage_'] img"),
                (By.CSS_SELECTOR, "img"),
            ]

            for by, selector in image_selectors:
                try:
                    img_elem = product_element.find_element(by, selector)
                    img_url = img_elem.get_attribute("src") or img_elem.get_attribute("data-src")
                    if img_url:
                        product['image_url'] = img_url
                        break
                except NoSuchElementException:
                    continue

            # Product URL - try new MUI selector first
            link_selectors = [
                (By.CSS_SELECTOR, "[data-testid='Link']"),
                (By.CSS_SELECTOR, "a[href*='.html']"),
                (By.XPATH, ".//a[contains(@href, '/p/')]"),
                (By.XPATH, ".//a[contains(@class, 'description')]"),
                (By.XPATH, ".//span[contains(@class, 'description')]//a"),
                (By.XPATH, ".//*[contains(@class, 'product-title')]//a"),
                (By.XPATH, ".//a[@automation-id='productDescriptionLink']"),
            ]

            for by, selector in link_selectors:
                try:
                    link_elem = product_element.find_element(by, selector)
                    href = link_elem.get_attribute("href")
                    if href and ('.html' in href or '/p/' in href):
                        if not href.startswith('http'):
                            href = f"https://www.costco.com{href}"
                        product['product_url'] = href
                        break
                except NoSuchElementException:
                    continue

            # Extract Costco product ID from URL if not already set
            if not product.get('costco_id') and product.get('product_url'):
                id_match = re.search(r'[/.](\d{6,})(?:\.html|\?|$)', product['product_url'])
                if id_match:
                    product['costco_id'] = id_match.group(1)

            # Brand - not typically shown in new MUI tiles, but try
            try:
                brand_elem = product_element.find_element(By.XPATH, ".//*[contains(@class, 'brand')]")
                brand_text = brand_elem.text.strip()
                if brand_text:
                    product['brand'] = brand_text
            except NoSuchElementException:
                pass

            return product if product.get('name') else None

        except Exception as e:
            print(f"  Error extracting product: {e}")
            return None

    def scrape_product_details(self, product: Dict) -> Dict:
        """Scrape additional details from the product detail page including nutritional info"""
        if not product.get('product_url'):
            return product

        try:
            print(f"    Fetching details for: {product['name'][:40]}...")
            self.driver.get(product['product_url'])
            time.sleep(2)

            # Product Description
            description_selectors = [
                "//*[@itemprop='description']",
                "//*[contains(@class, 'product-description')]",
                "//*[@id='product-description']",
                "//*[contains(@class, 'product-info-description')]",
            ]

            for selector in description_selectors:
                try:
                    desc_elem = self.driver.find_element(By.XPATH, selector)
                    desc_text = desc_elem.text.strip()
                    if desc_text:
                        product['description'] = desc_text
                        break
                except NoSuchElementException:
                    continue

            # Product Details section
            product_details_text = ""
            details_selectors = [
                "//*[@id='product-details']",
                "//*[contains(@class, 'product-details')]",
                "//*[@data-testid='product-details']",
                "//*[contains(@class, 'product-info-details')]",
            ]

            for selector in details_selectors:
                try:
                    details_elem = self.driver.find_element(By.XPATH, selector)
                    product_details_text = details_elem.text.strip()
                    if product_details_text:
                        break
                except NoSuchElementException:
                    continue

            # Specifications section
            specs_text = ""
            specs_selectors = [
                "//*[@id='product-specifications']",
                "//*[contains(@class, 'product-specifications')]",
                "//*[@data-testid='specifications']",
                "//*[contains(@class, 'specifications-table')]",
                "//*[@id='specifications']",
            ]

            for selector in specs_selectors:
                try:
                    specs_elem = self.driver.find_element(By.XPATH, selector)
                    specs_text = specs_elem.text.strip()
                    if specs_text:
                        break
                except NoSuchElementException:
                    continue

            # Store raw product details and specifications
            if product_details_text:
                product['raw_product_details'] = product_details_text
            if specs_text:
                product['raw_specifications'] = specs_text

            # Combine for description
            combined_details = ""
            if product_details_text:
                combined_details = f"PRODUCT DETAILS:\n{product_details_text}"
            if specs_text:
                if combined_details:
                    combined_details += f"\n\nSPECIFICATIONS:\n{specs_text}"
                else:
                    combined_details = f"SPECIFICATIONS:\n{specs_text}"

            if combined_details:
                if product.get('description'):
                    product['description'] = f"{product['description']}\n\n{combined_details}"
                else:
                    product['description'] = combined_details

            # Extract nutritional information
            all_text = f"{product_details_text} {specs_text}"
            all_text_lower = all_text.lower()

            # Calories
            cal_patterns = [
                r'calories[:\s]*(\d+)',
                r'(\d+)\s*calories',
                r'cal[:\s]*(\d+)',
            ]
            for pattern in cal_patterns:
                cal_match = re.search(pattern, all_text_lower)
                if cal_match:
                    product['calories'] = int(cal_match.group(1))
                    break

            # Protein
            protein_patterns = [
                r'protein[:\s]*(\d+)\s*g',
                r'(\d+)\s*g\s*protein',
            ]
            for pattern in protein_patterns:
                protein_match = re.search(pattern, all_text_lower)
                if protein_match:
                    product['protein'] = int(protein_match.group(1))
                    break

            # Carbs
            carb_patterns = [
                r'(?:total\s+)?carb(?:ohydrate)?s?[:\s]*(\d+)\s*g',
                r'(\d+)\s*g\s*(?:total\s+)?carb',
            ]
            for pattern in carb_patterns:
                carb_match = re.search(pattern, all_text_lower)
                if carb_match:
                    product['carbs'] = int(carb_match.group(1))
                    break

            # Fat
            fat_patterns = [
                r'(?:total\s+)?fat[:\s]*(\d+)\s*g',
                r'(\d+)\s*g\s*(?:total\s+)?fat',
            ]
            for pattern in fat_patterns:
                fat_match = re.search(pattern, all_text_lower)
                if fat_match:
                    product['fat'] = int(fat_match.group(1))
                    break

            # Sodium
            sodium_patterns = [
                r'sodium[:\s]*(\d+)\s*mg',
                r'(\d+)\s*mg\s*sodium',
            ]
            for pattern in sodium_patterns:
                sodium_match = re.search(pattern, all_text_lower)
                if sodium_match:
                    product['sodium'] = int(sodium_match.group(1))
                    break

            # Fiber
            fiber_patterns = [
                r'(?:dietary\s+)?fiber[:\s]*(\d+)\s*g',
                r'(\d+)\s*g\s*(?:dietary\s+)?fiber',
            ]
            for pattern in fiber_patterns:
                fiber_match = re.search(pattern, all_text_lower)
                if fiber_match:
                    product['fiber'] = int(fiber_match.group(1))
                    break

            # Sugar
            sugar_patterns = [
                r'(?:total\s+)?sugar[s]?[:\s]*(\d+)\s*g',
                r'(\d+)\s*g\s*(?:total\s+)?sugar',
            ]
            for pattern in sugar_patterns:
                sugar_match = re.search(pattern, all_text_lower)
                if sugar_match:
                    product['sugar'] = int(sugar_match.group(1))
                    break

            # Serving size
            serving_match = re.search(r'serving size[:\s]*([^\n,\.]+)', all_text, re.IGNORECASE)
            if serving_match:
                product['serving_size'] = serving_match.group(1).strip()[:100]

            # Ingredients
            ingredients_match = re.search(r'ingredients?[:\s]*([^\n]+(?:\n[^\n]+)*?)(?=\n\s*\n|allergen|contains|$)', all_text, re.IGNORECASE)
            if ingredients_match:
                ingredients = ingredients_match.group(1).strip()
                if len(ingredients) > 20:
                    product['ingredients'] = ingredients[:2000]

            # Allergens
            allergen_patterns = [
                r'(?:contains|allergen)[:\s]*([^\n]+)',
                r'(?:may contain)[:\s]*([^\n]+)',
            ]
            allergens = []
            for pattern in allergen_patterns:
                allergen_match = re.search(pattern, all_text, re.IGNORECASE)
                if allergen_match:
                    allergens.append(allergen_match.group(1).strip())
            if allergens:
                product['allergens'] = "; ".join(allergens)[:500]

            # Package size
            package_patterns = [
                r'(\d+(?:\.\d+)?\s*(?:oz|lb|lbs|count|ct|pk|pack))',
                r'(\d+\s*x\s*\d+(?:\.\d+)?\s*(?:oz|lb))',
            ]
            for pattern in package_patterns:
                pkg_match = re.search(pattern, all_text_lower)
                if pkg_match:
                    product['package_size'] = pkg_match.group(1).strip()
                    break

            # Unit price
            unit_price_match = re.search(r'\$[\d.]+/(?:oz|lb|ct|count)', all_text_lower)
            if unit_price_match:
                product['unit_price'] = unit_price_match.group(0)

        except Exception as e:
            print(f"    Error fetching product details: {e}")

        return product

    def scrape_category(self, category_name: str, url: str) -> List[Dict]:
        """Scrape all products from a category page"""
        print(f"\n{'='*60}")
        print(f"Scraping: {category_name}")
        print(f"URL: {url}")
        print(f"{'='*60}")

        products = []

        try:
            print("  Loading page...")
            self.driver.get(url)
            time.sleep(5)

            # Check for bot detection
            page_content = self.driver.page_source.lower()
            if "access denied" in page_content or "robot" in page_content or "captcha" in page_content:
                print("  Bot detection triggered - waiting and retrying...")
                time.sleep(10)
                self.driver.refresh()
                time.sleep(5)

            # Wait for products to load
            print("  Waiting for products to load...")
            product_loaded = False
            wait_selectors = [
                (By.CSS_SELECTOR, "[automation-id='productList']"),
                (By.CSS_SELECTOR, ".product-list"),
                (By.CSS_SELECTOR, ".product-grid"),
                (By.CSS_SELECTOR, "a[href*='/p/']"),
            ]

            for by, selector in wait_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((by, selector))
                    )
                    product_loaded = True
                    print(f"  Found content with selector: {selector}")
                    break
                except TimeoutException:
                    continue

            if not product_loaded:
                print("  Waiting additional time for products to load...")
                time.sleep(5)

            # Scroll to load lazy-loaded products
            print("  Scrolling to load all products...")
            for i in range(8):
                self.driver.execute_script("window.scrollBy(0, window.innerHeight)")
                time.sleep(0.5)
            self.driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(1)

            # Find all product cards - Costco now uses MUI with data-testid attributes
            product_selectors = [
                # New MUI-based selectors (current Costco site)
                "[data-testid^='ProductTile_']",
                # Legacy selectors (kept for fallback)
                "[automation-id='productList'] .product",
                "[automation-id='productList'] > div",
                ".product-list .product",
                ".product-tile-set .product",
                ".product-grid .col-xs-6",
                ".product-grid [class*='col-']",
                ".product",
                "div[data-testid='product']",
                ".product-tile",
            ]

            product_cards = []
            used_selector = None

            for selector in product_selectors:
                try:
                    cards = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(cards) > 0:
                        product_cards = cards
                        used_selector = selector
                        print(f"  Found {len(product_cards)} products using selector: {selector}")
                        break
                except Exception:
                    continue

            if not product_cards:
                # Alternate approach: find product links and traverse to parents
                print("  Trying alternate approach: finding product links...")
                try:
                    links = self.driver.find_elements(By.CSS_SELECTOR, "a[href*='/p/']")
                    seen_urls = set()
                    for link in links:
                        try:
                            href = link.get_attribute("href")
                            if href and href not in seen_urls:
                                seen_urls.add(href)
                                # Get parent container
                                parent = link.find_element(By.XPATH, "./ancestor::div[contains(@class, 'product') or contains(@class, 'col-')]")
                                product_cards.append(parent)
                        except:
                            continue
                    if product_cards:
                        print(f"  Found {len(product_cards)} products via link traversal")
                except Exception as e:
                    print(f"  Alternate approach failed: {e}")

            if not product_cards:
                print(f"  No products found on {category_name}")
                print("  DEBUG: Dumping page structure to help identify correct selectors...")
                try:
                    # Save full page HTML for inspection
                    with open(f"debug_{category_name}.html", "w", encoding="utf-8") as f:
                        f.write(self.driver.page_source)
                    print(f"  DEBUG: Saved full page HTML to debug_{category_name}.html")

                    # Find all elements that might be products
                    all_divs_with_classes = self.driver.execute_script("""
                        var results = [];
                        var elements = document.querySelectorAll('div[class], article, section');
                        for (var i = 0; i < Math.min(elements.length, 100); i++) {
                            var el = elements[i];
                            if (el.className && el.querySelector('img') && el.querySelector('a')) {
                                results.push({
                                    tag: el.tagName,
                                    classes: el.className,
                                    dataAttrs: Object.keys(el.dataset).join(', ')
                                });
                            }
                        }
                        return results;
                    """)
                    print("  DEBUG: Potential product container elements found:")
                    seen_classes = set()
                    for item in all_divs_with_classes[:20]:
                        class_key = item['classes'][:80]
                        if class_key not in seen_classes:
                            seen_classes.add(class_key)
                            print(f"    <{item['tag']} class=\"{item['classes'][:80]}...\" data-*=\"{item['dataAttrs']}\">")
                except Exception as e:
                    print(f"  DEBUG error: {e}")
                return products

            # Extract data from each product card
            for i, card in enumerate(product_cards, 1):
                try:
                    product = self.scrape_product_card(card, category_name)
                    if product:
                        products.append(product)
                        print(f"  [{i}/{len(product_cards)}] {product['name'][:50]}...")
                    else:
                        print(f"  [{i}/{len(product_cards)}] Skipped (invalid data)")

                except Exception as e:
                    print(f"  [{i}/{len(product_cards)}] Error: {e}")
                    continue

            # Optionally scrape product detail pages
            if SCRAPE_PRODUCT_DETAILS and products:
                print(f"\n  Fetching detailed product information...")
                for i, product in enumerate(products, 1):
                    try:
                        product = self.scrape_product_details(product)
                        time.sleep(random.uniform(1, 2))
                    except Exception as e:
                        print(f"    Error getting details for product {i}: {e}")

            print(f"\n  Successfully scraped {len(products)} products from {category_name}")

        except Exception as e:
            print(f"  Error scraping category {category_name}: {e}")
            import traceback
            traceback.print_exc()

        return products

    def save_to_database(self, products: List[Dict]) -> int:
        """Save products to Supabase database"""
        if not products:
            return 0

        print(f"\nSaving {len(products)} products to database...")
        saved_count = 0

        for product in products:
            try:
                # Skip products without a URL (required for upsert)
                if not product.get('product_url'):
                    print(f"  Skipping '{product.get('name', 'Unknown')[:30]}' - no product_url")
                    continue

                result = self.supabase.table('costco_products').upsert(
                    product,
                    on_conflict='product_url'
                ).execute()
                saved_count += 1

            except Exception as e:
                print(f"  Error saving product '{product.get('name', 'Unknown')[:30]}': {e}")
                # Print the product data for debugging
                print(f"    Product data: {product}")
                continue

        print(f"  Successfully saved {saved_count}/{len(products)} products")
        return saved_count

    def run(self):
        """Main scraping workflow"""
        print("="*60)
        print("COSTCO INVENTORY SCRAPER FOR FUELRX")
        print("Using undetected-chromedriver for bot detection bypass")
        print("="*60)
        print(f"Target warehouse: {WAREHOUSE_ADDRESS}")
        print(f"Categories to scrape: {len(CATEGORIES)}")
        print("="*60)

        all_products = []

        try:
            print(f"\nLaunching Chrome browser...")
            self.driver = self.create_driver()

            # Navigate to Costco
            print("Navigating to Costco.com...")
            self.driver.get("https://www.costco.com")
            time.sleep(5)

            # Handle cookie consent / popups
            try:
                popup_selectors = [
                    "//button[contains(text(), 'Accept')]",
                    "//button[contains(text(), 'Close')]",
                    "//button[contains(text(), 'Got it')]",
                    "//*[@aria-label='Close']",
                    "//*[contains(@class, 'modal-close')]",
                    "//*[@id='onetrust-accept-btn-handler']",
                ]
                for selector in popup_selectors:
                    try:
                        popup_btn = WebDriverWait(self.driver, 2).until(
                            EC.element_to_be_clickable((By.XPATH, selector))
                        )
                        popup_btn.click()
                        print(f"  Closed popup with: {selector}")
                        time.sleep(1)
                    except TimeoutException:
                        continue
            except:
                pass

            # Set warehouse location
            self.set_warehouse(WAREHOUSE_ZIP)

            # Scrape each category
            for i, (category_name, url) in enumerate(CATEGORIES.items()):
                try:
                    products = self.scrape_category(category_name, url)
                    all_products.extend(products)

                    # Save batch to database after each category
                    if products:
                        self.save_to_database(products)

                    # Random delay between categories
                    if i < len(CATEGORIES) - 1:
                        delay = random.uniform(5, 10)
                        print(f"\nWaiting {delay:.1f}s before next category...")
                        time.sleep(delay)

                except Exception as e:
                    print(f"Failed to scrape {category_name}: {e}")
                    import traceback
                    traceback.print_exc()
                    time.sleep(10)
                    continue

        finally:
            if self.driver:
                self.driver.quit()

        # Final summary
        print("\n" + "="*60)
        print("SCRAPING COMPLETE")
        print("="*60)
        print(f"Total products scraped: {len(all_products)}")
        print(f"Categories processed: {len(CATEGORIES)}")
        print("="*60)


def main():
    """Entry point"""
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

    if not supabase_url or not supabase_key:
        print("ERROR: Missing environment variables!")
        print("Please set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        print("\nExample:")
        print("export SUPABASE_URL='https://your-project.supabase.co'")
        print("export SUPABASE_SERVICE_ROLE_KEY='your-service-role-key'")
        return

    scraper = CostcoScraper(supabase_url, supabase_key)
    scraper.run()


if __name__ == "__main__":
    main()
