import asyncio
import os
import logging
import streamlit as st
from requests.auth import HTTPBasicAuth
import requests
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables (optional for local testing)
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

# Function to generate blog content
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
        content = response["choices"][0]["message"]["content"]
        logging.info("Generated blog content for title: %s", blog_title)
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
            return True
        else:
            logging.error("Failed to create post. Status Code: %d, Response: %s", response.status_code, response.text)
            return False
    except Exception as e:
        logging.error("Failed to publish blog post: %s", str(e))
        return False

# Streamlit UI
st.title("Automated WordPress Blog Post Creator")

# Input fields for user-defined title, topic, and keywords
blog_title = st.text_input("Enter the blog title:", placeholder="e.g., The Future of AI in Software Development")
blog_topic = st.text_input("Enter the blog topic:", placeholder="e.g., Artificial Intelligence in Development")
keywords = st.text_area("Enter keywords (comma-separated):", placeholder="e.g., AI, software development, innovation")

# Generate blog post on button click
if st.button("Generate and Publish Blog Post"):
    if not blog_title or not blog_topic or not keywords:
        st.error("Please fill in the blog title, topic, and keywords before proceeding.")
    else:
        # Process keywords into a list
        keyword_list = [kw.strip() for kw in keywords.split(",") if kw.strip()]
        
        # Log start of process
        logging.info("Starting blog generation with title: %s", blog_title)
        
        # Generate blog content
        with st.spinner("Generating blog content..."):
            blog_content = asyncio.run(generate_blog_content(blog_title, blog_topic, keyword_list))
        
        if blog_content:
            # Publish the blog post
            with st.spinner("Publishing blog post to WordPress..."):
                success = publish_blog_post(blog_title, blog_content)
            
            if success:
                st.success("Blog post published successfully!")
            else:
                st.error("Failed to publish blog post. Check the logs for details.")
        else:
            st.error("Failed to generate blog content. Check the logs for details.")
