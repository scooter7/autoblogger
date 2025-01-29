import asyncio
import os
import logging
import streamlit as st
from requests.auth import HTTPBasicAuth
import requests
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime
import threading
import time

# Load environment variables
load_dotenv()

# Fetch secrets and environment variables with fallback handling
domain = st.secrets.get("WP_DOMAIN") or os.getenv("WP_DOMAIN")
username = st.secrets.get("WP_USERNAME") or os.getenv("WP_USERNAME")
app_password = st.secrets.get("WP_APP_PASSWORD") or os.getenv("WP_APP_PASSWORD")
openai_api_key = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")

# Ensure all required secrets are present
if not all([domain, username, app_password, openai_api_key]):
    raise KeyError("One or more required secrets (WP_DOMAIN, WP_USERNAME, WP_APP_PASSWORD, OPENAI_API_KEY) are missing.")

# WordPress site details
endpoint = "/wp-json/wp/v2/posts/"
url = f"{domain}{endpoint}"

# Configure logging
logging.basicConfig(
    filename='app.log',
    filemode='a',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Initialize OpenAI client
client = OpenAI(api_key=openai_api_key)

# Global Variables for Cron Job
cron_stop_event = threading.Event()  # Event to stop the cron job
cron_thread = None  # Stores the cron job thread
cron_topic = None  # Stores the topic for cron-generated posts
cron_keywords = None  # Stores the keywords for cron-generated posts


async def generate_blog_content(blog_title, blog_topic, keywords):
    """
    Uses OpenAI to generate a blog post based on the given title, topic, and keywords.
    """
    prompt = (
        f"Create a detailed 15-minute read blog post titled '{blog_title}'. "
        f"Focus on the topic: '{blog_topic}' and incorporate the following keywords: {', '.join(keywords)}. "
        f"The blog should be well-structured for developers and businesses, using proper HTML tags like <h1>, <h2>, <p>, "
        f"and <code>. Include practical examples, analysis, and applications."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{'role': 'user', 'content': prompt}]
        )
        content = response.choices[0].message.content
        logging.info("Generated blog content for title: %s", blog_title)
        return content
    except Exception as e:
        logging.error("Failed to generate blog content: %s", str(e))
        return None


async def generate_blog_title(blog_topic, keywords):
    """
    Uses OpenAI to generate a relevant blog title based on the topic and keywords.
    """
    prompt = (
        f"Generate an engaging and professional blog post title for the topic '{blog_topic}' "
        f"incorporating the keywords: {', '.join(keywords)}. The title should be between 10-20 words, unique, and relevant."
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{'role': 'user', 'content': prompt}]
        )
        title = response.choices[0].message.content.strip().strip('"')
        logging.info("Generated blog title: %s", title)
        return title
    except Exception as e:
        logging.error("Failed to generate blog title: %s", str(e))
        return "Untitled Blog Post"


def publish_blog_post(blog_post_title, blog_content):
    """
    Publishes the blog post to WordPress.
    """
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
            return True
        else:
            logging.error("Failed to create post. Status Code: %d, Response: %s", response.status_code, response.text)
            return False
    except Exception as e:
        logging.error("Failed to publish blog post: %s", str(e))
        return False


def cron_function():
    """
    A cron-like function that generates and publishes a blog post every 30 minutes.
    """
    global cron_topic, cron_keywords  

    interval = 1800  # 30 minutes in seconds

    while not cron_stop_event.is_set():  # Only run while stop event is NOT set
        logging.info("Cron job started: Checking if it's time to post.")

        # Generate a relevant title dynamically
        blog_title = asyncio.run(generate_blog_title(cron_topic, cron_keywords))

        logging.info("Generating blog content for: %s", blog_title)
        blog_content = asyncio.run(generate_blog_content(blog_title, cron_topic, cron_keywords))

        if blog_content:
            logging.info("Publishing blog post: %s", blog_title)
            publish_blog_post(blog_title, blog_content)
        else:
            logging.error("Cron job: Failed to generate blog content")

        logging.info("Cron job completed. Next run in 30 minutes.")

        # Sleep for 30 minutes, but check every 5 seconds if stop event is set
        for _ in range(interval // 5):
            if cron_stop_event.is_set():
                logging.info("Cron job stopping...")
                return
            time.sleep(5)


def start_cron_job(topic, keywords):
    """
    Starts the cron job with user-specified topic and keywords.
    """
    global cron_thread, cron_topic, cron_keywords
    cron_topic = topic
    cron_keywords = keywords
    cron_stop_event.clear()  # Ensure the stop flag is cleared

    if cron_thread is None or not cron_thread.is_alive():
        cron_thread = threading.Thread(target=cron_function, daemon=True)
        cron_thread.start()
        logging.info("Cron job thread started.")

def stop_cron_job():
    """
    Stops the cron job.
    """
    cron_stop_event.set()  # Signal the thread to stop
    logging.info("Cron job has been stopped.")

# Display cron job status
st.subheader("Cron Job Status")

if "cron_thread" in st.session_state and st.session_state["cron_thread"] is not None:
    if st.session_state["cron_thread"].is_alive():
        st.warning("🚨 Cron job is currently running!")
    else:
        st.success("✅ Cron job is NOT running.")
else:
    st.success("✅ Cron job is NOT running.")

# Streamlit UI
st.title("Automated WordPress Blog Post Creator")

# User Input
blog_title = st.text_input("Enter the blog title:", placeholder="e.g., The Future of AI in Software Development")
blog_topic = st.text_input("Enter the blog topic:", placeholder="e.g., Artificial Intelligence in Development")
keywords = st.text_area("Enter keywords (comma-separated):", placeholder="e.g., AI, software development, innovation")

# Cron Job Checkbox
use_for_cron = st.checkbox("Use this topic and keywords for automated posting")

# Start/Stop Cron Job
if st.button("Start Cron Job", key="start_cron_button"):
    with st.spinner("Starting the cron job..."):
        start_cron_job(blog_topic, keywords.split(","))
        st.success("Cron job started!")

if st.button("Stop Cron Job", key="stop_cron_button"):
    with st.spinner("Stopping the cron job..."):
        stop_cron_job()
        st.success("Cron job stopped.")

# Manual Post Generation
if st.button("Generate and Publish Blog Post", key="manual_generate_button"):
    blog_content = asyncio.run(generate_blog_content(blog_title, blog_topic, keywords.split(",")))
    if blog_content:
        publish_blog_post(blog_title, blog_content)
        st.success("Blog post published successfully!")
