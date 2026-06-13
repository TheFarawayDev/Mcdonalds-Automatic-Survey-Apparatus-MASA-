"""
Happy Meal Web - McDonald's Survey Automator with Web Interface
FOR EDUCATIONAL PURPOSES ONLY
"""

from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException
import threading
import time
import random
import re
import json
import os
from datetime import datetime
from PIL import Image
import pytesseract
import base64
import io
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

# ============= CONFIGURATION =============
class Config:
    MIN_CREW_MEMBERS = 2  # Minimum to avoid suspicion
    MAX_SURVEYS_PER_MONTH = 5
    DELAY_BETWEEN_SURVEYS = (60, 120)  # 1-2 minutes
    
    @staticmethod
    def load_reviews():
        """Load comments from reviews.json"""
        default_comments = [
            f"The service from {{crew_name}} was absolutely amazing! ⭐",
            f"{{crew_name}} provided outstanding customer service today!",
            f"Shout out to {{crew_name}} for making my visit great! 🎉"
        ]
        try:
            if os.path.exists('reviews.json'):
                with open('reviews.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get('comments', default_comments)
            return default_comments
        except:
            return default_comments
    
    @staticmethod
    def load_config():
        """Load survey configuration"""
        default_config = {
            "order_placement": "With an employee at the restaurant",
            "visit_type": "Drive-thru",
            "overall_satisfaction": "Highly Satisfied",
            "rewards_member": "No",
            "order_accuracy_rating": "Highly Satisfied",
            "food_temperature_rating": "Highly Satisfied",
            "order_accurate": "Yes",
            "ease_of_ordering": "Highly Satisfied",
            "speed_of_service": "Highly Satisfied",
            "overall_value": "Highly Satisfied",
            "order_categories": ["Burgers, Chicken & Fish", "Beverages & Coffee"],
            "food_items": ["Chicken Nuggets", "Hamburger/Cheeseburger", "Fries"],
            "beverages": ["Soft Drink"],
            "soft_drink_quality": "Highly Satisfied",
            "fries_quality": "Highly Satisfied",
            "chicken_nuggets_quality": "Highly Satisfied",
            "burger_quality": "Highly Satisfied",
            "friendliness": "Highly Satisfied",
            "taste_of_food": "Highly Satisfied",
            "quality_of_food": "Highly Satisfied",
            "problem_experienced": "No",
            "likely_return": "Highly Likely",
            "likely_recommend": "Highly Likely",
            "pull_forward": "No",
            "visit_frequency_30_days": "Two",
            "favorite_restaurant": "McDonald’s",
            "brand_trust": "Strongly Agree",
            "gender": "Prefer not to answer",
            "age": "Other or prefer not to answer",
            "children_under_13": "No",
            "household_income": "Prefer not to answer",
            "ethnicity": "Prefer not to answer"
        }
        try:
            if os.path.exists('config.json'):
                with open('config.json', 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in default_config.items():
                        if key not in data:
                            data[key] = value
                    return data
            return default_config
        except:
            return default_config

# ============= SURVEY BOT =============
active_sessions = {}

class SurveyBotWeb:
    """Web-enabled survey bot with progress streaming"""
    
    def __init__(self, session_id, survey_code, crew_names, config, reviews):
        self.session_id = session_id
        self.survey_code = survey_code
        self.crew_names = crew_names
        self.config = config
        self.reviews = reviews
        self.results = {}
        self.is_running = True
        
    def emit_progress(self, message, page=None, total=None, status='info'):
        """Send progress update via WebSocket"""
        if not self.is_running:
            return
        socketio.emit('progress', {
            'session_id': self.session_id,
            'message': message,
            'page': page,
            'total': total,
            'status': status,
            'timestamp': datetime.now().isoformat()
        }, namespace='/survey')
    
    def get_random_comment(self, crew_name):
        """Get random comment with crew name inserted"""
        template = random.choice(self.reviews)
        return template.format(crew_name=crew_name)
    
    def click_radio_by_text(self, driver, text, timeout=3):
        """Click radio button by text"""
        try:
            strategies = [
                (By.XPATH, f"//label[contains(text(), '{text}')]"),
                (By.XPATH, f"//span[contains(text(), '{text}')]/ancestor::label"),
                (By.XPATH, f"//input[@type='radio' and @value='{text}']")
            ]
            for by, selector in strategies:
                try:
                    element = WebDriverWait(driver, timeout).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    element.click()
                    return True
                except:
                    continue
            return False
        except:
            return False
    
    def click_next(self, driver):
        """Click Next button"""
        try:
            for text in ['Next', 'Submit', 'Continue']:
                try:
                    btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.XPATH, f"//button[contains(text(), '{text}')]"))
                    )
                    btn.click()
                    time.sleep(1)
                    return True
                except:
                    continue
            return False
        except:
            return False
    
    def fill_text_area(self, driver, text):
        """Fill textarea"""
        try:
            textarea = driver.find_element(By.XPATH, "//textarea")
            textarea.clear()
            textarea.send_keys(text)
            return True
        except:
            return False
    
    def run_survey_for_crew(self, crew_name):
        """Run single survey for a crew member"""
        options = Options()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument("--headless")  # Run in background
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        driver = webdriver.Chrome(options=options)
        
        try:
            self.emit_progress(f"Starting survey for {crew_name}...", status='start')
            driver.get("https://www.mcdvoice.com")
            time.sleep(3)
            
            # Enter survey code
            code_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='text']"))
            )
            code_input.send_keys(self.survey_code)
            self.click_next(driver)
            
            # CAPTCHA - need manual intervention
            self.emit_progress(f"⚠️ CAPTCHA required for {crew_name}. Please solve manually in browser window...", status='warning')
            
            # Wait for manual CAPTCHA solving (30 seconds)
            time.sleep(30)
            
            # Page 1: Order placement
            self.click_radio_by_text(driver, self.config['order_placement'])
            self.click_next(driver)
            
            # Page 2: Visit type
            self.click_radio_by_text(driver, self.config['visit_type'])
            self.click_next(driver)
            
            # Page 3: Overall satisfaction
            self.click_radio_by_text(driver, self.config['overall_satisfaction'])
            self.click_next(driver)
            
            # Page 4: Rewards
            self.click_radio_by_text(driver, self.config['rewards_member'])
            self.click_next(driver)
            
            # Page 5: Quality ratings
            self.click_radio_by_text(driver, self.config['order_accuracy_rating'])
            self.click_radio_by_text(driver, self.config['food_temperature_rating'])
            self.click_next(driver)
            
            # Page 6: Order accurate
            self.click_radio_by_text(driver, self.config['order_accurate'])
            self.click_next(driver)
            
            # Page 7: Ease, speed, value
            self.click_radio_by_text(driver, self.config['ease_of_ordering'])
            self.click_radio_by_text(driver, self.config['speed_of_service'])
            self.click_radio_by_text(driver, self.config['overall_value'])
            self.click_next(driver)
            
            # Page 8: Categories
            for cat in self.config['order_categories']:
                self.click_checkbox_by_text(driver, cat)
            self.click_next(driver)
            
            # Page 9: Food items
            for item in self.config['food_items']:
                self.click_checkbox_by_text(driver, item)
            self.click_next(driver)
            
            # Page 10: Beverages
            for bev in self.config['beverages']:
                self.click_checkbox_by_text(driver, bev)
            self.click_next(driver)
            
            # Page 11: Food quality
            self.click_radio_by_text(driver, self.config['soft_drink_quality'])
            self.click_radio_by_text(driver, self.config['fries_quality'])
            self.click_radio_by_text(driver, self.config['chicken_nuggets_quality'])
            self.click_radio_by_text(driver, self.config['burger_quality'])
            self.click_next(driver)
            
            # Page 12: Service quality
            self.click_radio_by_text(driver, self.config['friendliness'])
            self.click_radio_by_text(driver, self.config['taste_of_food'])
            self.click_radio_by_text(driver, self.config['quality_of_food'])
            self.click_next(driver)
            
            # Page 13: Problems
            self.click_radio_by_text(driver, self.config['problem_experienced'])
            self.click_next(driver)
            
            # Page 14: Likelihood
            self.click_radio_by_text(driver, self.config['likely_return'])
            self.click_radio_by_text(driver, self.config['likely_recommend'])
            self.click_next(driver)
            
            # Page 15: Pull forward
            self.click_radio_by_text(driver, self.config['pull_forward'])
            self.click_next(driver)
            
            # Page 16: COMMENT
            comment = self.get_random_comment(crew_name)
            self.fill_text_area(driver, comment)
            self.click_next(driver)
            
            # Page 17: Frequency
            self.click_radio_by_text(driver, self.config['visit_frequency_30_days'])
            self.click_next(driver)
            
            # Page 18: Favorite
            self.click_checkbox_by_text(driver, self.config['favorite_restaurant'])
            self.click_next(driver)
            
            # Page 19: Brand trust
            self.click_radio_by_text(driver, self.config['brand_trust'])
            self.click_next(driver)
            
            # Page 20: Gender
            self.click_radio_by_text(driver, self.config['gender'])
            self.click_next(driver)
            
            # Page 21: Age
            self.click_radio_by_text(driver, self.config['age'])
            self.click_next(driver)
            
            # Page 22: Children
            self.click_radio_by_text(driver, self.config['children_under_13'])
            self.click_next(driver)
            
            # Page 23: Income
            self.click_radio_by_text(driver, self.config['household_income'])
            self.click_next(driver)
            
            # Page 24: Ethnicity
            self.click_radio_by_text(driver, self.config['ethnicity'])
            self.click_next(driver)
            
            # Get validation code
            time.sleep(3)
            page_text = driver.find_element(By.TAG_NAME, "body").text
            code_match = re.search(r'Validation Code:?\s*(\d{6,8})', page_text)
            validation_code = code_match.group(1) if code_match else None
            
            if not validation_code:
                code_match = re.search(r'(\d{7})', page_text)
                validation_code = code_match.group(1) if code_match else None
            
            self.results[crew_name] = {
                "validation_code": validation_code,
                "timestamp": datetime.now().isoformat(),
                "comment_used": comment
            }
            
            self.emit_progress(f"✅ Completed {crew_name}! Validation: {validation_code}", status='success')
            return validation_code
            
        except Exception as e:
            self.emit_progress(f"❌ Error for {crew_name}: {str(e)}", status='error')
            return None
        finally:
            driver.quit()
    
    def click_checkbox_by_text(self, driver, text):
        """Click checkbox by label text"""
        try:
            strategies = [
                (By.XPATH, f"//label[contains(text(), '{text}')]"),
                (By.XPATH, f"//input[@type='checkbox' and following-sibling::label[contains(text(), '{text}')]]")
            ]
            for by, selector in strategies:
                try:
                    element = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((by, selector))
                    )
                    element.click()
                    return True
                except:
                    continue
            return False
        except:
            return False
    
    def run(self):
        """Run all surveys"""
        total = len(self.crew_names)
        self.emit_progress(f"🚀 Starting {total} survey(s) with minimum {Config.MIN_CREW_MEMBERS} crew members", status='start')
        
        for idx, crew_name in enumerate(self.crew_names, 1):
            if not self.is_running:
                break
                
            self.emit_progress(f"📋 Survey {idx}/{total}: {crew_name}", status='progress')
            self.run_survey_for_crew(crew_name)
            
            if idx < total and self.is_running:
                delay = random.randint(*Config.DELAY_BETWEEN_SURVEYS)
                self.emit_progress(f"⏳ Waiting {delay} seconds before next survey...", status='info')
                time.sleep(delay)
        
        # Save results
        filename = f"results_{self.session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        self.emit_progress(f"✅ All surveys completed! Results saved to {filename}", status='complete')
        socketio.emit('complete', {
            'session_id': self.session_id,
            'results': self.results
        }, namespace='/survey')
        
        return self.results

# ============= FLASK ROUTES =============
@app.route('/')
def index():
    """Serve the main page"""
    return render_template('index.html', min_crew=Config.MIN_CREW_MEMBERS)

@app.route('/api/upload_receipt', methods=['POST'])
def upload_receipt():
    """Upload receipt image and extract code"""
    try:
        data = request.json
        image_data = data.get('image', '').split(',')[1]
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # OCR processing
        text = pytesseract.image_to_string(image)
        
        # Extract survey code pattern
        patterns = [
            r'\d{5}-\d{5}-\d{5}-\d{5}-\d{5}-\d{1}',
            r'\d{5}-\d{5}-\d{5}-\d{5}-\d{5}-\d{2}',
            r'Survey Code:?\s*(\d{5}-\d{5}-\d{5}-\d{5}-\d{5}-\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                code = match.group(0) if match.groups() else match.group(1) if match.groups() else match.group(0)
                code = code.replace('Survey Code:', '').strip()
                return jsonify({'success': True, 'code': code})
        
        return jsonify({'success': False, 'error': 'No survey code found'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/start', methods=['POST'])
def start_survey():
    """Start a new survey session"""
    data = request.json
    survey_code = data.get('survey_code', '').strip()
    crew_names = data.get('crew_names', [])
    
    # Validate minimum crew members
    if len(crew_names) < Config.MIN_CREW_MEMBERS:
        return jsonify({
            'success': False, 
            'error': f'Minimum {Config.MIN_CREW_MEMBERS} crew members required to avoid suspicious patterns'
        })
    
    if len(crew_names) > Config.MAX_SURVEYS_PER_MONTH:
        return jsonify({
            'success': False,
            'error': f'Maximum {Config.MAX_SURVEYS_PER_MONTH} surveys per month per restaurant'
        })
    
    if not survey_code:
        return jsonify({'success': False, 'error': 'Survey code required'})
    
    # Validate code format
    if not re.match(r'\d{5}-\d{5}-\d{5}-\d{5}-\d{5}-\d', survey_code):
        return jsonify({'success': False, 'error': 'Invalid survey code format'})
    
    session_id = str(uuid.uuid4())
    config = Config.load_config()
    reviews = Config.load_reviews()
    
    bot = SurveyBotWeb(session_id, survey_code, crew_names, config, reviews)
    active_sessions[session_id] = bot
    
    # Run in background thread
    thread = threading.Thread(target=bot.run)
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'session_id': session_id})

@app.route('/api/stop/<session_id>', methods=['POST'])
def stop_survey(session_id):
    """Stop a running survey session"""
    if session_id in active_sessions:
        active_sessions[session_id].is_running = False
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Session not found'})

@socketio.on('connect', namespace='/survey')
def handle_connect():
    """Handle WebSocket connection"""
    emit('connected', {'message': 'Connected to survey service'})

if __name__ == '__main__':
    print(f"""
    🍔 Happy Meal Web - McDonald's Survey Automator
    ================================================
    🌐 Web interface: http://localhost:5000
    📋 Minimum crew members: {Config.MIN_CREW_MEMBERS}
    🔢 Max surveys per month: {Config.MAX_SURVEYS_PER_MONTH}
    
    FOR EDUCATIONAL PURPOSES ONLY
    """)
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)
