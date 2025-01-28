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


async def generate_blog_content(blog_title, blog_topic, keywords):
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
        st.error(f"Error generating blog content: {e}")
        return None


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
    while True:
        try:
            # Define dynamic inputs for automation
            blog_title = f"Automated Post {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            blog_topic = "Technology Trends"
            keywords = ["AI", "software development", "automation"]

            logging.info("Cron job started: Generating blog content")
            blog_content = asyncio.run(generate_blog_content(blog_title, blog_topic, keywords))

            if blog_content:
                logging.info("Cron job: Publishing blog content")
                publish_blog_post(blog_title, blog_content)
            else:
                logging.error("Cron job: Failed to generate blog content")

            # Wait for 30 minutes before generating the next post
            time.sleep(1800)  # 30 minutes
        except Exception as e:
            logging.error("Cron job failed: %s", str(e))


def start_cron_job_in_background():
    """
    Starts the cron job in a separate thread.
    """
    thread = threading.Thread(target=cron_function, daemon=True)
    thread.start()
    return thread


# Streamlit UI
st.title("Automated WordPress Blog Post Creator")

# Input fields for user-defined title, topic, and keywords
blog_title = st.text_input("Enter the blog title:", placeholder="e.g., The Future of AI in Software Development")
blog_topic = st.text_input("Enter the blog topic:", placeholder="e.g., Artificial Intelligence in Development")
keywords = st.text_area("Enter keywords (comma-separated):", placeholder="e.g., AI, software development, innovation")

# Start the cron job
if st.button("Start Cron Job"):
    with st.spinner("Starting the cron job..."):
        start_cron_job_in_background()
        st.success("Cron job started! The app will generate and publish a new post every 30 minutes.")

# Manual trigger for generating and publishing blog posts
if st.button("Generate and Publish Blog Post"):
    if not blog_title or not blog_topic or not keywords:
        st.error("Please fill in the blog title, topic, and keywords before proceeding.")
    else:
        keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]

        with st.spinner("Generating blog content..."):
            blog_content = asyncio.run(generate_blog_content(blog_title, blog_topic, keyword_list))

        if blog_content:
            with st.spinner("Publishing blog post to WordPress..."):
                success = publish_blog_post(blog_title, blog_content)

            if success:
                st.success("Blog post published successfully!")
            else:
                st.error("Failed to publish blog post. Check the logs for details.")
        else:
            st.error("Failed to generate blog content. Check the logs for details.")
