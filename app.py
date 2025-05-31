import streamlit as st
import requests
import random
import json
from openai import OpenAI
import os
from datetime import datetime
from PIL import Image
import io
import base64
from urllib.parse import urlencode

# File to track posted keywords
POSTED_KEYWORDS_FILE = "posted_keywords.txt"

def load_posted_keywords():
    """Load previously posted keywords from file."""
    if os.path.exists(POSTED_KEYWORDS_FILE):
        with open(POSTED_KEYWORDS_FILE, 'r') as f:
            return [line.strip().lower() for line in f.readlines()]
    return []

def save_posted_keyword(keyword):
    """Save a new posted keyword to file."""
    with open(POSTED_KEYWORDS_FILE, 'a') as f:
        f.write(f"{keyword.lower()}\n")




client = OpenAI(api_key = st.secrets["api_key"])



def generate_hashtags(keywords, count=20):
    base_tags = [f"#{keyword.strip().replace(' ', '').title()}" for keyword in keywords if len(keyword.strip()) > 2]
    
    # Add generic high-traffic tags
    generic_tags = [
        "#AI", "#MachineLearning", "#DataScience", "#Tech", "#Innovation", "#CareerGrowth", 
        "#Python", "#Coding", "#BigData", "#Analytics", "#FutureOfWork", "#Leadership",
        "#Productivity", "#Motivation", "#Learning", "#WorkCulture", "#ProfessionalDevelopment",
        "#DigitalTransformation", "#CloudComputing", "#Automation", "#DevOps", "#Business"
    ]
    
    all_tags = list(dict.fromkeys(base_tags + generic_tags))  # Remove duplicates
    return " ".join(all_tags[:count])  # Ensure minimum of 20

def generate_dynamic_post(keywords):
    prompt = f"""
    Write a LinkedIn post of more than 150 words about: {', '.join(keywords)}.
    The post should be informative, inspiring, and formatted like a human wrote it.
    Include at least 20 relevant hashtags at the end.
    Avoid em dashes (—) in the post.
    """
    
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a professional LinkedIn content writer."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=600
    )
    
    return response.choices[0].message.content.strip()


def linkedin_auth_url():
    """Generate LinkedIn OAuth URL."""
    client_id = st.secrets.get("LINKEDIN_CLIENT_ID", "")
    redirect_uri = "http://localhost:8501"
    
    params = {
        'response_type': 'code',
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'scope': 'profile openid email w_member_social',
        'state': 'linkedin_auth'
    }
    
    return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"

def get_access_token(auth_code):
    """Exchange auth code for access token."""
    token_url = "https://www.linkedin.com/oauth/v2/accessToken"
    
    data = {
        'grant_type': 'authorization_code',
        'code': auth_code,
        'client_id': st.secrets.get("LINKEDIN_CLIENT_ID", ""),
        'client_secret': st.secrets.get("LINKEDIN_CLIENT_SECRET", ""),
        'redirect_uri': 'http://localhost:8501'
    }
    
    response = requests.post(token_url, data=data)
    if response.status_code == 200:
        return response.json()['access_token']
    else:
        raise Exception(f"Token exchange failed: {response.text}")

def upload_image_to_linkedin(access_token, image_data):
    """Upload image to LinkedIn."""
    
    # Step 1: Get person ID
    profile_url = "https://api.linkedin.com/v2/userinfo"
    headers = {'Authorization': f'Bearer {access_token}'}
    profile_response = requests.get(profile_url, headers=headers)
    
    if profile_response.status_code != 200:
        raise Exception("Failed to get profile info")
    
    person_id = profile_response.json()['sub']
    
    # Step 2: Register upload
    register_url = "https://api.linkedin.com/rest/images?action=initializeUpload"
    register_data = {
        "initializeUploadRequest": {
            "owner": f"urn:li:person:{person_id}"
        }
    }
    
    headers['Content-Type'] = 'application/json'
    headers['LinkedIn-Version'] = '202505'
    
    register_response = requests.post(register_url, headers=headers, json=register_data)
    
    if register_response.status_code != 200:
        raise Exception(f"Upload registration failed: {register_response.text}")
    
    upload_info = register_response.json()['value']
    upload_url = upload_info['uploadUrl']
    image_urn = upload_info['image']
    
    # Step 3: Upload image
    upload_headers = {'Authorization': f'Bearer {access_token}'}
    upload_response = requests.put(upload_url, headers=upload_headers, data=image_data)
    
    if upload_response.status_code not in [200, 201]:
        raise Exception(f"Image upload failed: {upload_response.text}")
    
    return image_urn

def post_to_linkedin(access_token, content, image_urn=None):
    """Post content to LinkedIn."""
    
    # Get person ID
    profile_url = "https://api.linkedin.com/v2/userinfo"
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'LinkedIn-Version': '202505'
    }
    
    profile_response = requests.get(profile_url, headers=headers)
    if profile_response.status_code != 200:
        raise Exception("Failed to get profile info")
    
    person_id = profile_response.json()['sub']
    
    # Create post data
    post_data = {
        "author": f"urn:li:person:{person_id}",
        "commentary": content,
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": []
        },
        "lifecycleState": "PUBLISHED"
    }
    
    # Add image if provided
    if image_urn:
        post_data["content"] = {
            "media": {
                "title": "Post Image",
                "id": image_urn
            }
        }
    
    # Post to LinkedIn
    post_url = "https://api.linkedin.com/rest/posts"
    response = requests.post(post_url, headers=headers, json=post_data)
    
    if response.status_code == 201:
        return response.json()
    else:
        raise Exception(f"Post failed: {response.text}")

def main():
    st.set_page_config(
        page_title="Simple LinkedIn Poster",
        page_icon="🚀",
        layout="centered"
    )
    
    st.title("🚀 Simple LinkedIn Poster")
    st.markdown("*Keywords + Image → Humanized LinkedIn Post*")
    st.markdown("---")
    
    # Check if LinkedIn credentials are configured
    if not st.secrets.get("LINKEDIN_CLIENT_ID") or not st.secrets.get("LINKEDIN_CLIENT_SECRET"):
        st.error("⚠️ Please configure LinkedIn credentials in Streamlit secrets:")
        st.code('''
LINKEDIN_CLIENT_ID = "your_client_id"
LINKEDIN_CLIENT_SECRET = "your_client_secret"
        ''')
        st.info("Get these from: https://developer.linkedin.com")
        return
    
        # Authentication Section
    st.subheader("🔐 LinkedIn Authentication")

    # Use updated method to get query params
    query_params = st.query_params
    code_from_url = query_params.get("code")

    if 'linkedin_token' not in st.session_state:
        if code_from_url:
            try:
                token = get_access_token(code_from_url)
                st.session_state.linkedin_token = token
                st.success("✅ LinkedIn connected successfully via redirect!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Auto-authentication failed: {str(e)}")
        else:
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button("🔗 Connect LinkedIn", type="primary"):
                    auth_url = linkedin_auth_url()
                    st.markdown(f"👉 [Click here to authorize LinkedIn]({auth_url})")

            with col2:
                auth_code = st.text_input("Paste authorization code here:")
                if st.button("✅ Submit") and auth_code:
                    try:
                        token = get_access_token(auth_code)
                        st.session_state.linkedin_token = token
                        st.success("✅ LinkedIn connected successfully!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Authentication failed: {str(e)}")
    else:
        st.success("✅ LinkedIn connected!")
        if st.button("🔓 Disconnect"):
            del st.session_state.linkedin_token
            st.rerun()


    
    st.markdown("---")
    
    # Only show posting interface if authenticated
    if 'linkedin_token' in st.session_state:
        
        # Show previously posted keywords
        posted_keywords = load_posted_keywords()
        if posted_keywords:
            st.subheader("📝 Previously Posted Keywords")
            st.info(f"Already posted: {', '.join(posted_keywords[-10:])}")  # Show last 10
        
        st.subheader("✍️ Create New Post")
        
        # Keywords input
        keywords_input = st.text_input(
            "🔍 Enter keywords (comma-separated):",
            placeholder="AI, machine learning, innovation, future"
        )
        
        # Image upload
        uploaded_image = st.file_uploader(
            "🖼️ Upload image:",
            type=['png', 'jpg', 'jpeg'],
            help="Optional: Add an image to your post"
        )
        
        # Show image preview
        if uploaded_image:
            image = Image.open(uploaded_image)
            st.image(image, caption="Image Preview", width=300)
        
        # Generate post preview
        if keywords_input:
            keywords = [k.strip() for k in keywords_input.split(',') if k.strip()]
            
            # Check if keywords already posted
            already_posted = []
            for keyword in keywords:
                if keyword.lower() in posted_keywords:
                    already_posted.append(keyword)
            
            if already_posted:
                st.warning(f"⚠️ Already posted about: {', '.join(already_posted)}")
            
            # Generate preview
            if st.button("👀 Preview Post"):
                generated_content = generate_dynamic_post(keywords)
                st.session_state.preview_content = generated_content
            
            # Show preview
            if 'preview_content' in st.session_state:
                st.subheader("📖 Post Preview")
                st.write(st.session_state.preview_content)
                
                # Edit option
                edited_content = st.text_area(
                    "✏️ Edit post (optional):",
                    value=st.session_state.preview_content,
                    height=200
                )
                
                # Post button
                if st.button("🚀 Post to LinkedIn", type="primary"):
                    try:
                        with st.spinner("Posting to LinkedIn..."):
                            
                            # Upload image if provided
                            image_urn = None
                            if uploaded_image:
                                image_data = uploaded_image.getvalue()
                                image_urn = upload_image_to_linkedin(st.session_state.linkedin_token, image_data)
                            
                            # Post to LinkedIn
                            result = post_to_linkedin(
                                st.session_state.linkedin_token, 
                                edited_content, 
                                image_urn
                            )
                            
                            # Save keywords to file
                            for keyword in keywords:
                                save_posted_keyword(keyword)
                            
                            st.success("🎉 Successfully posted to LinkedIn!")
                            
                            # Clear session state
                            if 'preview_content' in st.session_state:
                                del st.session_state.preview_content
                            
                            st.balloons()
                            
                    except Exception as e:
                        st.error(f"❌ Posting failed: {str(e)}")
    
    # Instructions
    st.markdown("---")
    st.subheader("📋 How to Use")
    st.markdown("""
    1. **Connect LinkedIn**: Authorize the app with your LinkedIn account
    2. **Enter Keywords**: Add comma-separated keywords for your post topic
    3. **Upload Image** (optional): Add a visual element to your post
    4. **Preview**: Generate and review your humanized post
    5. **Post**: Share it to your LinkedIn feed!
    
    The app automatically:
    - ✅ Creates humanized, engaging content
    - ✅ Adds relevant hashtags
    - ✅ Tracks posted keywords to avoid duplicates
    - ✅ Handles image uploads
    """)

if __name__ == "__main__":
    main()