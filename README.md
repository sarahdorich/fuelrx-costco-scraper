# Costco Inventory Scraper for FuelRx

This Python script scrapes Costco's website for your Sandy, UT warehouse and stores the inventory in your Supabase database.

## Setup Instructions

### 1. Run the Database Migration

First, apply the new migration to create the `costco_products` table:

```bash
# In your Supabase dashboard:
# 1. Go to SQL Editor
# 2. Copy and paste the contents of supabase/migrations/002_costco_products.sql
# 3. Run the migration

# OR use the Supabase CLI if you have it installed:
supabase db push
```

### 2. Install Python Dependencies

Using the Makefile:

```bash
make install
source venv/bin/activate
```

Manual setup:

```bash
# Create a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

### 3. Set Environment Variables

You need your Supabase credentials. Get these from your Supabase dashboard:

1. Go to Project Settings > API
2. Copy your **Project URL** (looks like `https://xxxxx.supabase.co`)
3. Copy your **service_role key** (NOT the anon key - you need admin access)

Create a `.env` file or export them:

```bash
# Option 1: Create .env file
echo 'SUPABASE_URL=https://your-project.supabase.co' > .env
echo 'SUPABASE_SERVICE_ROLE_KEY=your-service-role-key' >> .env

# Option 2: Export directly (Mac/Linux)
export SUPABASE_URL='https://your-project.supabase.co'
export SUPABASE_SERVICE_ROLE_KEY='your-service-role-key'

# Option 2: Set for session (Windows)
set SUPABASE_URL=https://your-project.supabase.co
set SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
```

### 4. Run the Scraper

```bash
# If using .env file:
python3 costco_scraper.py

# If you exported variables, just run:
python3 costco_scraper.py
```

## What the Scraper Does

1. **Opens Costco.com** in a browser (Playwright handles JavaScript rendering)
2. **Sets your warehouse** to Sandy, UT (zip: 84070)
3. **Scrapes these categories:**
   - Meat & Seafood
   - Deli
   - Prepared Meals & Food
   - Pantry & Dry Goods
   - Organic
   - Cheese & Dairy
   - Snacks
   - Mixt Pantry
4. **Extracts product data:**
   - Name, brand, price
   - Image URL
   - Product URL
   - Category
5. **Saves to your Supabase database** in the `costco_products` table

## Running Options

### Headless Mode (No Browser Window)
Edit `costco_scraper.py` line 195:
```python
browser: Browser = p.chromium.launch(headless=True)  # Change to True
```

### Run Manually When Needed
Just run the script whenever you want to update inventory:
```bash
python3 costco_scraper.py
```

### Schedule It (Optional)
Add to crontab to run weekly:
```bash
# Edit crontab
crontab -e

# Add this line to run every Sunday at 2am
0 2 * * 0 cd /path/to/fuel-rx && /path/to/venv/bin/python costco_scraper.py
```

## Troubleshooting

### "No products found"
- Costco may have changed their HTML structure
- Check the browser window (run with `headless=False`) to see what's happening
- You may need to update the CSS selectors in `scrape_product_card()`

### "Warehouse not set" warning
- The scraper will continue anyway
- Products shown may not be available at your warehouse
- You can manually check by opening Costco.com and verifying your warehouse is set

### Rate Limiting
- The scraper includes 2-3 second delays between requests
- If you get blocked, increase the delays in the code
- Consider running during off-peak hours

### Database Errors
- Make sure you're using the **service_role key**, not the anon key
- Check that the migration ran successfully
- Verify RLS policies allow inserts from service role

## Database Query Examples

Once data is in your database, you can query it from your Next.js app:

```typescript
// Get all meat products
const { data: meatProducts } = await supabase
  .from('costco_products')
  .select('*')
  .eq('category', 'meat_seafood')
  .eq('in_stock', true)

// Search for chicken products
const { data: chickenProducts } = await supabase
  .from('costco_products')
  .select('*')
  .ilike('name', '%chicken%')
  .eq('warehouse_location', 'Sandy, UT')

// Get products in a price range
const { data: affordableProducts } = await supabase
  .from('costco_products')
  .select('*')
  .gte('price', 5)
  .lte('price', 20)
```

## Next Steps

1. **Integrate with meal plans** - When Claude generates a meal plan, query the Costco database to suggest products
2. **Add nutrition data** - Scrape detailed product pages for nutritional info
3. **Track price history** - Instead of updating, insert new records to see price changes over time
4. **Web scraping for recipes** - Scrape Costco's recipe section for meal prep ideas

## Notes

- Costco's website structure may change, requiring updates to selectors
- Some products may not be available at your specific warehouse
- Nutritional data isn't always available on category pages (may need product detail page scraping)
- The scraper respects Costco's servers with delays between requests
- Consider Costco's Terms of Service regarding scraping
