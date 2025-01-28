import asyncio
import os
import random
import logging
import streamlit as st
from streamlit.runtime.scriptrunner import add_script_run_ctx
from requests.auth import HTTPBasicAuth
from datetime import datetime, timedelta
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (optional with `.env` for local testing)
load_dotenv()

# Configure Streamlit secrets
st.secrets = {
    "WP_USERNAME": os.getenv("WP_USERNAME") or st.secrets.get("WP_USERNAME"),
    "WP_APP_PASSWORD": os.getenv("WP_APP_PASSWORD") or st.secrets.get("WP_APP_PASSWORD"),
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY") or st.secrets.get("OPENAI_API_KEY"),
}

# WordPress site details
domain = st.secrets["WP_DOMAIN"]  # Store in secrets
endpoint = "/wp-json/wp/v2/posts/"
url = f"{domain}{endpoint}"
username = st.secrets["WP_USERNAME"]
app_password = st.secrets["WP_APP_PASSWORD"]

# Configure logging
logging.basicConfig(
    filename='app.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize OpenAI client
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

# List of seed words for dynamic blog post title generation
seed_words = [
    'Artificial Intelligence', 'Machine Learning', 'Web Development',
    'Python Programming', 'Java Development', 'Database Management',
    'React Development', 'Vue Framework', 'Tailwind CSS', 'Software Business Strategies'
]

# Function to generate blog post title
async def generate_blog_post_title():
    seed_word = random.choice(seed_words)
    message = {
        'role': 'user',
        'content': f'Generate one blog post title on "{seed_word}" targeted at tech enthusiasts and developers. It should be clear, professional, and ready for use.'
    }

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[message]
        )
        title = response["choices"][0]["message"]["content"].strip()
        logging.info("Generated blog post title: %s", title)
        return title
    except Exception as e:
        logging.error("Failed to generate blog post title: %s", str(e))
        return None

# Function to generate blog content
async def generate_blog_content(blog_post_title):
    message = {
        'role': 'user',
        'content': f"Create a 15-minute read blog post titled '{blog_post_title}' for software developers. Use proper HTML structure with <h1>, <h2>, <p>, <b>, and <code> tags. Include practical examples and applications."
    }

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[message]
        )
        content = response["choices"][0]["message"]["content"]
        logging.info("Generated blog content for title: %s", blog_post_title)
        return content
    except Exception as e:
        logging.error("Failed to generate blog content: %s", str(e))
        return None

# Function to publish blog post on WordPress
def publish_blog_post(blog_post_title, blog_content):
    post_data = {
        'title': blog_post_title,
        'content': blog_content,
        'status': 'publish'
    }

    try:
        response = requests.post(
            url,
            auth=HTTPBasicAuth(username, app_password),
            json=post_data
        )

        if response.status_code == 201:
            logging.info("Post created successfully! Post ID: %s", response.json().get('id'))
        else:
            logging.error("Failed to create post. Status Code: %d, Response: %s", response.status_code, response.text)
    except Exception as e:
        logging.error("Failed to publish blog post: %s", str(e))

# Function to handle blog creation flow
async def create_blog_post():
    try:
        blog_post_title = await generate_blog_post_title()
        if not blog_post_title:
            return

        blog_content = await generate_blog_content(blog_post_title)
        if not blog_content:
            return

        publish_blog_post(blog_post_title, blog_content)
    except Exception as e:
        logging.error("Error in creating blog post: %s", str(e))

# Cron-like function within the app
def cron_like_function(interval_minutes=30):
    next_run = datetime.now() + timedelta(minutes=interval_minutes)
    while True:
        if datetime.now() >= next_run:
            asyncio.run(create_blog_post())
            next_run = datetime.now() + timedelta(minutes=interval_minutes)

# Streamlit UI
st.title("Automated WordPress Blog Post Creator")
if st.button("Start Blog Automation"):
    logging.info("Blog automation started.")
    add_script_run_ctx(asyncio.create_task(cron_like_function()))
    st.success("Blog automation has started! Check logs for progress.")
