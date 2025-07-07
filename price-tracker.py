import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class ProductPriceTracker:
    def __init__(self):
        self.products = []
        self.price_history = {}
        
    def add_product(self, name, url, price_selector, target_price=None):
        """Add a product to track"""
        product = {
            'name': name,
            'url': url,
            'price_selector': price_selector,
            'target_price': target_price,
            'last_price': None
        }
        self.products.append(product)
        self.price_history[name] = []
        
    def get_price(self, url, selector):
        """Scrape price from product page"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            price_element = soup.select_one(selector)
            
            if price_element:
                # Extract price text and clean it
                price_text = price_element.get_text().strip()
                # Remove currency symbols and extract numeric value
                price = float(''.join(filter(str.isdigit, price_text.replace('.', '').replace(',', ''))) / 100)
                return price
            else:
                print(f"Price element not found for selector: {selector}")
                return None
                
        except Exception as e:
            print(f"Error scraping price: {e}")
            return None
    
    def track_products(self):
        """Track all products and check for price changes"""
        for product in self.products:
            current_price = self.get_price(product['url'], product['price_selector'])
            
            if current_price:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Store price history
                self.price_history[product['name']].append({
                    'price': current_price,
                    'timestamp': timestamp
                })
                
                # Check if price changed
                if product['last_price'] and current_price != product['last_price']:
                    print(f"Price change detected for {product['name']}")
                    print(f"Previous: ${product['last_price']:.2f}")
                    print(f"Current: ${current_price:.2f}")
                    
                    # Check if target price is reached
                    if product['target_price'] and current_price <= product['target_price']:
                        self.send_alert(product, current_price)
                
                product['last_price'] = current_price
                print(f"{product['name']}: ${current_price:.2f} - {timestamp}")
            else:
                print(f"Could not fetch price for {product['name']}")
    
    def send_alert(self, product, current_price):
        """Send email alert when target price is reached"""
        print(f"🎉 TARGET PRICE REACHED for {product['name']}!")
        print(f"Current price: ${current_price:.2f}")
        print(f"Target price: ${product['target_price']:.2f}")
        
        # Email configuration (you'll need to set up SMTP settings)
        # self.send_email_notification(product, current_price)
    
    def send_email_notification(self, product, current_price):
        """Send email notification (requires SMTP configuration)"""
        try:
            # Configure your email settings here
            smtp_server = "smtp.gmail.com"
            smtp_port = 587
            sender_email = "your_email@gmail.com"
            sender_password = "your_app_password"
            recipient_email = "recipient@gmail.com"
            
            msg = MIMEMultipart()
            msg['From'] = sender_email
            msg['To'] = recipient_email
            msg['Subject'] = f"Price Alert: {product['name']}"
            
            body = f"""
            Good news! The price for {product['name']} has dropped to your target price!
            
            Current Price: ${current_price:.2f}
            Target Price: ${product['target_price']:.2f}
            Product URL: {product['url']}
            
            Happy shopping!
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
            server.quit()
            
            print("Email notification sent successfully!")
            
        except Exception as e:
            print(f"Error sending email: {e}")
    
    def save_data(self, filename='price_history.json'):
        """Save price history to JSON file"""
        with open(filename, 'w') as f:
            json.dump(self.price_history, f, indent=2)
    
    def load_data(self, filename='price_history.json'):
        """Load price history from JSON file"""
        try:
            with open(filename, 'r') as f:
                self.price_history = json.load(f)
        except FileNotFoundError:
            print("No existing price history found.")
    
    def run_tracker(self, interval=3600):
        """Run the tracker continuously"""
        print("Starting price tracker...")
        self.load_data()
        
        while True:
            try:
                print(f"\n--- Checking prices at {datetime.now()} ---")
                self.track_products()
                self.save_data()
                print(f"Waiting {interval} seconds before next check...")
                time.sleep(interval)
            except KeyboardInterrupt:
                print("\nTracker stopped by user.")
                break
            except Exception as e:
                print(f"Error in tracker: {e}")
                time.sleep(60)  # Wait 1 minute before retrying

# Example usage
if __name__ == "__main__":
    tracker = ProductPriceTracker()
    
    # Add products to track (you'll need to inspect the HTML to find the correct selectors)
    tracker.add_product(
        name="Example Product 1",
        url="https://example-store.com/product1",
        price_selector=".price-current",  # CSS selector for price element
        target_price=50.00  # Alert when price drops to $50 or below
    )
    
    tracker.add_product(
        name="Example Product 2", 
        url="https://example-store.com/product2",
        price_selector=".product-price .price",
        target_price=100.00
    )
    
    # Run single check
    tracker.track_products()
    
    # Or run continuously (uncomment the line below)
    # tracker.run_tracker(interval=1800)  # Check every 30 minutes
