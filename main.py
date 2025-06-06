# imports from flask
import json
import os
import ast
import flask
from urllib.parse import urljoin, urlparse
from flask import abort, redirect, render_template, request, send_from_directory, url_for, jsonify  # import render_template from "public" flask libraries
from flask_login import current_user, login_user, logout_user
from flask.cli import AppGroup
from flask_login import current_user, login_required
from flask import current_app
from werkzeug.security import generate_password_hash
from flask_cors import CORS
import shutil
import datetime

# Additional imports from app.py for sentiment analysis and image prediction
from textblob import TextBlob
from collections import defaultdict
import random
import pandas as pd
import csv
import io
from sklearn.linear_model import LinearRegression
from PIL import Image, ImageStat
import numpy as np

# import "objects" from "this" project
from __init__ import app, db, login_manager  # Key Flask objects 

# Add CORS support
CORS(app, supports_credentials=True)

# API endpoints
from api.user import user_api 
from api.pfp import pfp_api
from api.nestImg import nestImg_api # Justin added this, custom format for his website
from api.post import post_api
from api.channel import channel_api
from api.group import group_api
from api.section import section_api
from api.nestPost import nestPost_api # Justin added this, custom format for his website
from api.messages_api import messages_api # Adi added this, messages for his website
from api.timeofdayapi import legoland_time_api
from api.vote import vote_api
from api.hashtag import hashtag_api
from api.length import length_bp

# database Initialization functions
from model.user import User, initUsers
from model.section import Section, initSections
from model.group import Group, initGroups
from model.channel import Channel, initChannels
from model.post import Post, initPosts
from model.nestPost import NestPost, initNestPosts # Justin added this, custom format for his website
from model.vote import Vote, initVotes
from model.frequency import FrequencySaver

# Import image model functions (conditional import to handle missing files gracefully)
try:
    from model.image import model, predict_likes_from_image, extract_image_features
    IMAGE_MODEL_AVAILABLE = True
except ImportError:
    print("Warning: Image model not available. Image prediction features will be disabled.")
    IMAGE_MODEL_AVAILABLE = False

# register URIs for api endpoints
app.register_blueprint(messages_api) # Adi added this, messages for his website
app.register_blueprint(user_api)
app.register_blueprint(pfp_api) 
app.register_blueprint(post_api)
app.register_blueprint(channel_api)
app.register_blueprint(group_api)
app.register_blueprint(section_api)
# Added new files to create nestPosts, uses a different format than Mortensen and didn't want to touch his junk
app.register_blueprint(nestPost_api)
app.register_blueprint(nestImg_api)
app.register_blueprint(vote_api)
app.register_blueprint(legoland_time_api)
app.register_blueprint(hashtag_api)
app.register_blueprint(length_bp)

# Tell Flask-Login the view function name of your login route
login_manager.login_view = "login"

@login_manager.unauthorized_handler
def unauthorized_callback():
    return redirect(url_for('login', next=request.path))

# register URIs for server pages
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.context_processor
def inject_user():
    return dict(current_user=current_user)

# Helper function to check if the URL is safe for redirects
def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

# Traditional login route (for server-side form submission)
@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    next_page = request.args.get('next', '') or request.form.get('next', '')
    if request.method == 'POST':
        user = User.query.filter_by(_uid=request.form['username']).first()
        if user and user.is_password(request.form['password']):
            login_user(user)
            if not is_safe_url(next_page):
                return abort(400)
            return redirect(next_page or url_for('index'))
        else:
            error = 'Invalid username or password.'
    return render_template("login.html", error=error, next=next_page)

# NEW API ENDPOINTS FOR AJAX LOGIN SYSTEM

@app.route('/api/authenticate', methods=['POST'])
def api_authenticate():
    """API endpoint for login - returns JSON"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No data provided'}), 400
            
        username = data.get('uid')  # Your frontend sends 'uid'
        password = data.get('password')
        
        if not username or not password:
            return jsonify({'message': 'Username and password required'}), 400
        
        user = User.query.filter_by(_uid=username).first()
        if user and user.is_password(password):
            login_user(user)
            return jsonify({
                'message': 'Login successful',
                'uid': user._uid,
                'name': user._name,
                'role': user._role if hasattr(user, '_role') else 'user'
            }), 200
        else:
            return jsonify({'message': 'Invalid username or password'}), 401
            
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({'message': 'Login failed'}), 500

@app.route('/api/id', methods=['GET'])
def api_get_user_id():
    """API endpoint to get current user info - returns JSON"""
    try:
        if current_user.is_authenticated:
            return jsonify({
                'uid': current_user._uid,
                'name': current_user._name,
                'role': current_user._role if hasattr(current_user, '_role') else 'user'
            }), 200
        else:
            return jsonify({'message': 'Not authenticated'}), 401
    except Exception as e:
        print(f"Get user ID error: {e}")
        return jsonify({'message': 'Error getting user info'}), 500

@app.route('/api/user', methods=['POST'])
def api_create_user():
    """API endpoint for user registration - returns JSON"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No data provided'}), 400
            
        name = data.get('name')
        uid = data.get('uid')
        password = data.get('password')
        
        if not all([name, uid, password]):
            return jsonify({'message': 'Name, uid, and password are required'}), 400
        
        # Check if user already exists
        existing_user = User.query.filter_by(_uid=uid).first()
        if existing_user:
            return jsonify({'message': 'User already exists'}), 409
        
        # Create new user
        user = User(name=name, uid=uid, password=password)
        user.create()
        
        return jsonify({
            'message': 'User created successfully',
            'uid': uid,
            'name': name
        }), 201
        
    except Exception as e:
        print(f"User creation error: {e}")
        return jsonify({'message': 'User creation failed'}), 500

@app.route('/api/user', methods=['PUT'])
def api_update_user():
    """API endpoint to update user info"""
    if not current_user.is_authenticated:
        return jsonify({'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'message': 'No data provided'}), 400
        
        # Update user fields
        if 'name' in data:
            current_user._name = data['name']
        if 'uid' in data:
            current_user._uid = data['uid']
        if 'password' in data:
            current_user.set_password(data['password'])
        
        # Save changes
        db.session.commit()
        
        return jsonify({'message': 'User updated successfully'}), 200
        
    except Exception as e:
        print(f"User update error: {e}")
        return jsonify({'message': 'Update failed'}), 500

@app.route('/api/user', methods=['GET'])
def api_get_user():
    """API endpoint to get user info"""
    if not current_user.is_authenticated:
        return jsonify({'message': 'Not authenticated'}), 401
    
    try:
        return jsonify({
            'uid': current_user._uid,
            'name': current_user._name,
            'role': current_user._role if hasattr(current_user, '_role') else 'user'
        }), 200
    except Exception as e:
        print(f"Get user error: {e}")
        return jsonify({'message': 'Error getting user info'}), 500

@app.route('/api/id/pfp', methods=['GET'])
def api_get_profile_picture():
    """API endpoint to get user profile picture"""
    if not current_user.is_authenticated:
        return jsonify({'message': 'Not authenticated'}), 401
    
    try:
        # Assuming your User model has a pfp field
        pfp_data = current_user._pfp if hasattr(current_user, '_pfp') else None
        return jsonify({
            'uid': current_user._uid,
            'name': current_user._name,
            'pfp': pfp_data
        }), 200
    except Exception as e:
        print(f"Get profile picture error: {e}")
        return jsonify({'message': 'Error getting profile picture'}), 500

@app.route('/api/id/pfp', methods=['PUT'])
def api_update_profile_picture():
    """API endpoint to update user profile picture"""
    if not current_user.is_authenticated:
        return jsonify({'message': 'Not authenticated'}), 401
    
    try:
        data = request.get_json()
        if not data or 'pfp' not in data:
            return jsonify({'message': 'No profile picture data provided'}), 400
        
        # Update profile picture
        current_user._pfp = data['pfp']
        db.session.commit()
        
        return jsonify({'message': 'Profile picture updated successfully'}), 200
        
    except Exception as e:
        print(f"Profile picture update error: {e}")
        return jsonify({'message': 'Profile picture update failed'}), 500

# =================================================================================
# SENTIMENT ANALYSIS FUNCTIONS AND ENDPOINTS (from app.py)
# =================================================================================

# Function to load comments from the CSV file
def get_comments_from_file():
    comments = []
    try:
        csv_path = os.path.join(os.path.dirname(__file__), 'api', 'legoland_comments_all_posts.csv')
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                comments.append(row['Comment'])  # Assuming 'Comment' is the correct column name
    except Exception as e:
        print(f"Error loading comments: {e}")
    return comments

# Function for sentiment analysis from CSV content
def analyze_sentiment_from_csv(csv_content):
    sentiments = []
    
    try:
        # Use StringIO to read CSV content
        csv_file = io.StringIO(csv_content)
        reader = csv.DictReader(csv_file)
        
        # Check if required column exists
        if 'Comment' not in reader.fieldnames:
            return {"error": "CSV file must contain a 'Comment' column"}, 400
        
        for row_num, row in enumerate(reader, start=2):  # Start at 2 since row 1 is header
            comment = row['Comment'].strip() if row['Comment'] else ''
            
            if comment:  # Only analyze non-empty comments
                blob = TextBlob(comment)
                polarity = blob.sentiment.polarity
                subjectivity = blob.sentiment.subjectivity
                
                # Categorize sentiment
                if polarity > 0.1:
                    category = "positive"
                elif polarity < -0.1:
                    category = "negative"
                else:
                    category = "neutral"
                
                sentiment_data = {
                    "row_number": row_num,
                    "comment": comment,
                    "polarity": round(polarity, 3),
                    "subjectivity": round(subjectivity, 3),
                    "category": category
                }
                
                # Include additional data if available
                if 'Name' in row and row['Name']:
                    sentiment_data['name'] = row['Name']
                if 'ProfileUrl' in row and row['ProfileUrl']:
                    sentiment_data['profile_url'] = row['ProfileUrl']
                if 'Likes' in row and row['Likes']:
                    try:
                        sentiment_data['likes'] = int(row['Likes'])
                    except ValueError:
                        sentiment_data['likes'] = 0
                if 'Date' in row and row['Date']:
                    sentiment_data['date'] = row['Date']
                
                sentiments.append(sentiment_data)
        
        if not sentiments:
            return {"error": "No valid comments found in the CSV file"}, 400
        
        # Calculate summary statistics
        avg_polarity = sum(item['polarity'] for item in sentiments) / len(sentiments)
        avg_subjectivity = sum(item['subjectivity'] for item in sentiments) / len(sentiments)
        
        # Count sentiment categories
        positive_count = len([s for s in sentiments if s['category'] == 'positive'])
        neutral_count = len([s for s in sentiments if s['category'] == 'neutral'])
        negative_count = len([s for s in sentiments if s['category'] == 'negative'])
        
        total_comments = len(sentiments)
        
        return {
            "success": True,
            "summary": {
                "total_comments": total_comments,
                "average_polarity": round(avg_polarity, 3),
                "average_subjectivity": round(avg_subjectivity, 3),
                "sentiment_counts": {
                    "positive": positive_count,
                    "neutral": neutral_count,
                    "negative": negative_count
                },
                "sentiment_percentages": {
                    "positive": round((positive_count / total_comments) * 100, 1),
                    "neutral": round((neutral_count / total_comments) * 100, 1),
                    "negative": round((negative_count / total_comments) * 100, 1)
                }
            },
            "comments": sentiments
        }
    
    except Exception as e:
        return {"error": f"Error processing CSV: {str(e)}"}, 500

# Add an API endpoint for sentiment analysis (original)
@app.route('/api/sentiment', methods=['GET'])
def analyze_sentiment():
    try:
        # Load CSV file with flexible path resolution
        csv_paths = [
            '/home/mihirthaha/nighthawk/healthmedia_backend-1/api/legoland_comments_all_posts.csv',
            os.path.join(os.path.dirname(__file__), 'api', 'legoland_comments_all_posts.csv'),
            'api/legoland_comments_all_posts.csv',
            'legoland_comments_all_posts.csv'
        ]
        
        df = None
        for csv_path in csv_paths:
            try:
                df = pd.read_csv(csv_path)
                break
            except FileNotFoundError:
                continue
        
        if df is None:
            return jsonify({"error": "CSV file not found in any expected location"})

        # Group comments by Post Shortcode
        grouped = defaultdict(list)
        for _, row in df.iterrows():
            grouped[row['Post Shortcode']].append(row['Comment'])

        # Get the 3 latest posts (assuming newest are at the top)
        latest_3_posts = list(grouped.keys())[:3]

        sentiment_results = {}
        for shortcode in latest_3_posts:
            comments = grouped[shortcode]
            if comments:
                scores = [TextBlob(comment).sentiment.polarity for comment in comments]
                average_score = sum(scores) / len(scores) if scores else 0
                sentiment_results[shortcode] = round(average_score, 3)
            else:
                sentiment_results[shortcode] = None  # no comments

        return jsonify(sentiment_results)

    except Exception as e:
        return jsonify({"error": str(e)})

# Add new API endpoint for CSV file upload and analysis
@app.route("/api/sentiment/upload", methods=["POST"])
def upload_and_analyze():
    """New endpoint for analyzing uploaded CSV files"""
    try:
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({"error": "No file uploaded"}), 400
        
        file = request.files['file']
        
        # Check if file was selected
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Check if file is CSV
        if not file.filename.lower().endswith('.csv'):
            return jsonify({"error": "File must be a CSV file"}), 400
        
        # Read file content
        try:
            csv_content = file.read().decode('utf-8')
        except UnicodeDecodeError:
            try:
                # Try with different encoding if UTF-8 fails
                file.seek(0)
                csv_content = file.read().decode('latin-1')
            except Exception as e:
                return jsonify({"error": "Unable to read file. Please ensure it's a valid CSV file."}), 400
        
        # Analyze sentiment
        result = analyze_sentiment_from_csv(csv_content)
        
        if isinstance(result, tuple):  # Error case
            return jsonify(result[0]), result[1]
        else:
            return jsonify(result)
    
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

# =================================================================================
# IMAGE PREDICTION FUNCTIONS AND ENDPOINTS (from app.py)
# =================================================================================

# Load dataset and train model once (with error handling)
try:
    likes_data = pd.read_csv('datasets/legoland.csv')
    X = likes_data[['Brightness', 'Saturation', 'Size']].values
    y = likes_data['numLikes'].values
    DATASET_AVAILABLE = True
except FileNotFoundError:
    print("Warning: Legoland dataset not found. Image prediction features will use mock data.")
    DATASET_AVAILABLE = False
    likes_data = None

def average_likes():
    if DATASET_AVAILABLE and likes_data is not None:
        total_likes = likes_data["numLikes"].sum()
        num_posts = len(likes_data["numLikes"])
        return total_likes / num_posts
    else:
        return 100  # Mock average for when dataset is not available

def classify_rating(score):
    if score >= 125:
        return "Excellent"
    elif score >= 115:
        return "Good"
    elif score >= 100:
        return "Moderate"
    else:
        return "Poor"

@app.route('/api/predict-likes', methods=['POST'])
def predict_likes():
    if not IMAGE_MODEL_AVAILABLE:
        return jsonify({'error': 'Image prediction model not available'}), 503
    
    file = request.files.get('image')
    if not file:
        return jsonify({'error': 'No image uploaded'}), 400

    temp_path = 'temp_image.jpg'
    file.save(temp_path)

    try:
        brightness, saturation, size = extract_image_features(temp_path)
        X_new = np.array([[brightness, saturation, size]])
        prediction = model.predict(X_new)[0]

        avg_likes = average_likes()
        rating_score = 100 * prediction / avg_likes
        rating_label = classify_rating(rating_score)

        return jsonify({
            'brightness': brightness,
            'saturation': saturation,
            'size': size,
            'predicted_likes': prediction,
            'rating_score': rating_score,
            'rating_label': rating_label
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

# =================================================================================
# ADDITIONAL ENDPOINTS FROM app.py
# =================================================================================

# Add an API endpoint to fetch some data
@app.route('/api/data')
def get_data():
    # Sample data to return
    InfoDb = []
    InfoDb.append({
        "FirstName": "John",
        "LastName": "Mortensen",
        "DOB": "October 21",
        "Residence": "San Diego",
        "Email": "jmortensen@powayusd.com",
        "Owns_Cars": ["2015-Fusion", "2011-Ranger", "2003-Excursion", "1997-F350", "1969-Cadillac"]
    })
    InfoDb.append({
        "FirstName": "Shane",
        "LastName": "Lopez",
        "DOB": "February 27",
        "Residence": "San Diego",
        "Email": "slopez@powayusd.com",
        "Owns_Cars": ["2021-Insight"]
    })
    
    return jsonify(InfoDb)

# Add an API endpoint to fetch an affirmation
@app.route('/api/affirmation')
def get_affirmation():
    affirmations = [
        "I am enough just as I am.",
        "I deserve love and respect.",
        "I choose to focus on my strengths.",
        "I am proud of the progress I've made.",
        "I trust myself to make the right decisions.",
        "I am capable of achieving great things.",
        "I radiate confidence and positivity.",
        "Challenges are opportunities for growth.",
        "I am in charge of my own destiny.",
        "My potential is limitless.",
        "I am strong and healthy.",
        "My body deserves care and nourishment.",
        "I honor my need for rest and rejuvenation.",
        "Every breath I take fills me with calm.",
        "I am grateful for my body and its abilities.",
        "I attract love and positivity.",
        "I communicate with honesty and kindness.",
        "I deserve meaningful connections.",
        "I am surrounded by supportive and loving people.",
        "I give and receive love freely."
    ]
    return jsonify(random.choice(affirmations))

# Add health check endpoint
@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "message": "API is running"})

# =================================================================================
# EXISTING MAIN.PY ROUTES CONTINUE
# =================================================================================
    
@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.errorhandler(404)  # catch for URL not found
def page_not_found(e):
    # note that we set the 404 status explicitly
    return render_template('404.html'), 404

@app.route('/')  # connects default URL to index() function
def index():
    print("Home:", current_user)
    return render_template("index.html")

@app.route('/users/table')
@login_required
def utable():
    users = User.query.all()
    return render_template("utable.html", user_data=users)

@app.route('/users/table2')
@login_required
def u2table():
    users = User.query.all()
    return render_template("u2table.html", user_data=users)

# Helper function to extract uploads for a user (ie PFP image)
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)
 
@app.route('/users/delete/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    user = User.query.get(user_id)
    if user:
        user.delete()
        return jsonify({'message': 'User deleted successfully'}), 200
    return jsonify({'error': 'User not found'}), 404

@app.route('/users/reset_password/<int:user_id>', methods=['POST'])
@login_required
def reset_password(user_id):
    if current_user.role != 'Admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    # Set the new password
    if user.update({"password": app.config['DEFAULT_PASSWORD']}):
        return jsonify({'message': 'Password reset successfully'}), 200
    return jsonify({'error': 'Password reset failed'}), 500

# Create an AppGroup for custom commands
custom_cli = AppGroup('custom', help='Custom commands')

# Define a command to run the data generation functions
@custom_cli.command('generate_data')
def generate_data():
    initUsers()
    initSections()
    initGroups()
    initChannels()
    initPosts()
    initVotes()
    initNestPosts()
    
# Backup the old database
def backup_database(db_uri, backup_uri):
    """Backup the current database."""
    if backup_uri:
        db_path = db_uri.replace('sqlite:///', 'instance/')
        backup_path = backup_uri.replace('sqlite:///', 'instance/')
        shutil.copyfile(db_path, backup_path)
        print(f"Database backed up to {backup_path}")
    else:
        print("Backup not supported for production database.")

# Extract data from the existing database
def extract_data():
    data = {}
    with app.app_context():
        data['users'] = [user.read() for user in User.query.all()]
        data['sections'] = [section.read() for section in Section.query.all()]
        data['groups'] = [group.read() for group in Group.query.all()]
        data['channels'] = [channel.read() for channel in Channel.query.all()]
        data['posts'] = [post.read() for post in Post.query.all()]
        return data

# Save extracted data to JSON files
def save_data_to_json(data, directory='backup'):
    if not os.path.exists(directory):
        os.makedirs(directory)
    for table, records in data.items():
        with open(os.path.join(directory, f'{table}.json'), 'w') as f:
            for record in records:
                if record.get('date_posted'):
                    record['date_posted'] = record['date_posted'].isoformat()
                if record.get('date_added'):
                    if type(record['date_added']) != str:
                        record['date_added'] = record['date_added'].isoformat()
            json.dump(records, f)
    print(f"Data backed up to {directory} directory.")

# Load data from JSON files
def load_data_from_json(directory='backup'):
    data = {}
    for table in ['users', 'sections', 'groups', 'channels', 'posts']:
        with open(os.path.join(directory, f'{table}.json'), 'r') as f:
            data[table] = json.load(f)
    return data

# Restore data to the new database
def restore_data(data):
    with app.app_context():
        users = User.restore(data['users'])
        _ = Section.restore(data['sections'])
        _ = Group.restore(data['groups'], users)
        _ = Channel.restore(data['channels'])
        _ = Post.restore(data['posts'])
    print("Data restored to the new database.")

# Define a command to backup data
@custom_cli.command('backup_data')
def backup_data():
    data = extract_data()
    save_data_to_json(data)
    backup_database(app.config['SQLALCHEMY_DATABASE_URI'], app.config['SQLALCHEMY_BACKUP_URI'])

# Define a command to restore data
@custom_cli.command('restore_data')
def restore_data_command():
    data = load_data_from_json()
    restore_data(data)
    
# Register the custom command group with the Flask application
app.cli.add_command(custom_cli)
        
# this runs the flask application on the development server
if __name__ == "__main__":
    # change name for testing
    app.run(debug=True, host="0.0.0.0", port="4891") #8106