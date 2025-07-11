import requests
from bs4 import BeautifulSoup
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import schedule
import time
import threading
from datetime import datetime
import json
import os
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

class PriceTracker:
    def __init__(self):
        self.csv_file = 'price_data.csv'
        self.config_file = 'config.json'
        self.init_csv()
        self.load_config()
        
    def init_csv(self):
        """Initialize CSV file with headers if it doesn't exist"""
        if not os.path.exists(self.csv_file):
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow(['timestamp', 'product_name', 'url', 'current_price', 'target_price', 'alert_sent'])
    
    def load_config(self):
        """Load email configuration"""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as file:
                self.config = json.load(file)
        else:
            self.config = {
                'email': {
                    'smtp_server': 'smtp.gmail.com',
                    'smtp_port': 587,
                    'sender_email': '',
                    'sender_password': '',
                    'recipient_email': ''
                }
            }
    
    def save_config(self, config):
        """Save email configuration"""
        self.config = config
        with open(self.config_file, 'w') as file:
            json.dump(config, file, indent=2)
    
    def get_headers(self):
        """Get headers to mimic a real browser request"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def extract_price_from_text(self, text):
        """Extract price from text using regex - supports Indian Rupees"""
        # Clean text and preserve Indian price formats
        cleaned_text = re.sub(r'[^\d.,₹\s]', ' ', text.replace('Rs.', '₹').replace('Rs', '₹').replace('INR', '₹'))
        
        # Indian price patterns (supports lakhs/crores format)
        indian_price_patterns = [
            r'₹\s*(\d{1,2}(?:,\d{2})*(?:,\d{3})*(?:\.\d{2})?)',  # ₹1,23,456.78
            r'₹\s*(\d{1,3}(?:,\d{2})*(?:,\d{3})*)',  # ₹1,23,456
            r'(\d{1,2}(?:,\d{2})*(?:,\d{3})*(?:\.\d{2})?)\s*₹',  # 1,23,456.78 ₹
            r'(\d{1,3}(?:,\d{2})*(?:,\d{3})*)\s*₹',  # 1,23,456 ₹
        ]
        
        # Try Indian patterns first
        for pattern in indian_price_patterns:
            matches = re.findall(pattern, cleaned_text)
            if matches:
                price_str = matches[0].replace(',', '')
                try:
                    return float(price_str)
                except ValueError:
                    continue
        
        # Fallback to general price patterns
        general_patterns = [
            r'(\d{1,3}(?:,\d{3})*(?:\.\d{2})?)',  # 1,234.56
            r'(\d+\.\d{2})',  # 123.45
            r'(\d+)',  # 123
        ]
        
        for pattern in general_patterns:
            matches = re.findall(pattern, cleaned_text)
            if matches:
                price_str = matches[0].replace(',', '')
                try:
                    price = float(price_str)
                    # Filter out unreasonably small prices (likely not actual prices)
                    if price > 1:
                        return price
                except ValueError:
                    continue
        
        return None
    
    def scrape_price(self, url, price_selector=None):
        """Scrape price from a given URL - optimized for Indian sites"""
        try:
            response = requests.get(url, headers=self.get_headers(), timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            if price_selector:
                # Use custom selector
                price_element = soup.select_one(price_selector)
                if price_element:
                    price = self.extract_price_from_text(price_element.get_text())
                    if price:
                        return price
            
            # Indian e-commerce site specific selectors
            indian_selectors = [
                # Flipkart
                '._30jeq3', '.CEmiEU', '._1_WHN1',
                # Amazon India
                '.a-price-whole', '.a-price-fraction', '.a-price-range',
                # Myntra
                '.pdp-price', '.discount-price',
                # Snapdeal
                '.payBlkBig', '.product-price',
                # Paytm Mall
                '._1kMS', '.price',
                # Nykaa
                '.css-1d0jdb', '.product-price',
                # FirstCry
                '.prod-price', '.price-tag',
                # BookMyShow
                '.price-tag', '.cost',
                # Zomato
                '.cost-for-two', '.price',
                # BigBasket
                '.discnt-price', '.price-tag',
            ]
            
            # Try Indian site selectors first
            for selector in indian_selectors:
                elements = soup.select(selector)
                for element in elements:
                    price = self.extract_price_from_text(element.get_text())
                    if price and price > 1:
                        return price
            
            # Common price selectors
            common_selectors = [
                '.price', '.price-current', '.price-now', '.current-price',
                '.sale-price', '.regular-price', '.amount', '.cost',
                '[data-price]', '[class*="price"]', '[id*="price"]',
                'span[class*="price"]', 'div[class*="price"]',
                '.price-display', '.price-value',
                # Indian currency specific
                '[class*="rupee"]', '[class*="inr"]', '[class*="₹"]',
                '.final-price', '.selling-price', '.offer-price',
            ]
            
            for selector in common_selectors:
                elements = soup.select(selector)
                for element in elements:
                    price = self.extract_price_from_text(element.get_text())
                    if price and price > 1:
                        return price
            
            # Fallback: search entire page for price patterns
            page_text = soup.get_text()
            price = self.extract_price_from_text(page_text)
            if price and price > 1:
                return price
                
        except Exception as e:
            print(f"Error scraping {url}: {str(e)}")
            return None
    
    def save_to_csv(self, product_name, url, current_price, target_price, alert_sent=False):
        """Save price data to CSV"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([timestamp, product_name, url, current_price, target_price, alert_sent])
    
    
    
    def send_alert(self, product_name, current_price, target_price, url):
        """Send email alert when price drops below target"""
        if not all([
            self.config['email']['sender_email'],
            self.config['email']['sender_password'],
            self.config['email']['recipient_email']
        ]):
            print("Email configuration incomplete. Cannot send alert.")
            return False
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.config['email']['sender_email']
            msg['To'] = self.config['email']['recipient_email']
            msg['Subject'] = f"🔔 Price Alert: {product_name}"
            
            body = f"""
            Great news! The price has dropped for the product you're tracking:
            
            Product: {product_name}
            Current Price: ₹{current_price:,.2f}
            Target Price: ₹{target_price:,.2f}
            Savings: ₹{target_price - current_price:,.2f}
            
            Product URL: {url}
            
            Happy shopping!
            """
            
            msg.attach(MIMEText(body, 'plain'))
            
            server = smtplib.SMTP(self.config['email']['smtp_server'], self.config['email']['smtp_port'])
            server.starttls()
            server.login(self.config['email']['sender_email'], self.config['email']['sender_password'])
            
            server.send_message(msg)
            server.quit()
            
            print(f"Alert sent for {product_name}")
            return True
            
        except Exception as e:
            print(f"Error sending email: {str(e)}")
            return False
    
    def check_price(self, product_name, url, target_price, price_selector=None):
        """Check price and send alert if needed"""
        current_price = self.scrape_price(url, price_selector)
        
        if current_price is None:
            print(f"Could not fetch price for {product_name}")
            return None
        
        print(f"{product_name}: ₹{current_price:,.2f} (Target: ₹{target_price:,.2f})")
        
        alert_sent = False
        if current_price <= target_price:
            alert_sent = self.send_alert(product_name, current_price, target_price, url)
        
        self.save_to_csv(product_name, url, current_price, target_price, alert_sent)
        
        return {
            'product_name': product_name,
            'current_price': current_price,
            'target_price': target_price,
            'alert_sent': alert_sent,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_price_history(self, product_name=None):
        """Get price history from CSV"""
        history = []
        
        if not os.path.exists(self.csv_file):
            return history
        
        with open(self.csv_file, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                if product_name is None or row['product_name'] == product_name:
                    history.append({
                        'timestamp': row['timestamp'],
                        'product_name': row['product_name'],
                        'url': row['url'],
                        'current_price': float(row['current_price']),
                        'target_price': float(row['target_price']),
                        'alert_sent': row['alert_sent'].lower() == 'true'
                    })
        
        return history

# Initialize tracker
tracker = PriceTracker()

# Store scheduled jobs
scheduled_jobs = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/track', methods=['POST'])
def track_price():
    data = request.json
    
    product_name = data.get('product_name')
    url = data.get('url')
    target_price = float(data.get('target_price'))
    price_selector = data.get('price_selector')
    
    result = tracker.check_price(product_name, url, target_price, price_selector)
    
    if result:
        return jsonify({'success': True, 'data': result})
    else:
        return jsonify({'success': False, 'error': 'Could not fetch price'})

@app.route('/api/schedule', methods=['POST'])
def schedule_tracking():
    data = request.json
    
    product_name = data.get('product_name')
    url = data.get('url')
    target_price = float(data.get('target_price'))
    interval = data.get('interval', 'hourly')
    price_selector = data.get('price_selector')

    job_key = f"{product_name}_{url}"

    # Cancel previous job if exists
    if job_key in scheduled_jobs:
        schedule.cancel_job(scheduled_jobs[job_key])

    # Define job
    def job():
        tracker.check_price(product_name, url, target_price, price_selector)

    # Schedule based on interval
    if interval == 'hourly':
        scheduled_jobs[job_key] = schedule.every().hour.do(job)
    elif interval == 'daily':
        scheduled_jobs[job_key] = schedule.every().day.do(job)
    elif interval == 'weekly':
        scheduled_jobs[job_key] = schedule.every().week.do(job)

    # 🔔 Send schedule-started alert email
    tracker.send_schedule_notification(product_name, target_price, interval, url)

    return jsonify({'success': True, 'message': f'Scheduled {interval} tracking for {product_name}'})


@app.route('/api/history')
def get_history():
    product_name = request.args.get('product_name')
    history = tracker.get_price_history(product_name)
    return jsonify(history)

@app.route('/api/config', methods=['GET', 'POST'])
def email_config():
    if request.method == 'GET':
        return jsonify(tracker.config)
    
    elif request.method == 'POST':
        config = request.json
        tracker.save_config(config)
        return jsonify({'success': True, 'message': 'Configuration saved'})

def run_scheduler():
    """Run the scheduler in a separate thread"""
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    # Start scheduler in background
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Run Flask app
    app.run(debug=True, host='0.0.0.0', port=5000)
