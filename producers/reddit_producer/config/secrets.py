"""
Secure credential management for Reddit API
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class RedditCredentials:
    """Reddit API credentials loaded from environment variables"""

    CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
    CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
    USER_AGENT = os.getenv('REDDIT_USER_AGENT')

    @classmethod
    def validate(cls):
        """Validate that all required credentials are present"""
        missing = []

        if not cls.CLIENT_ID:
            missing.append('REDDIT_CLIENT_ID')
        if not cls.CLIENT_SECRET:
            missing.append('REDDIT_CLIENT_SECRET')
        if not cls.USER_AGENT:
            missing.append('REDDIT_USER_AGENT')

        if missing:
            raise ValueError(
                f"Missing required Reddit credentials: {', '.join(missing)}. "
                f"Please create a .env file based on .env.template"
            )

        return True

    @classmethod
    def get_credentials(cls):
        """Get credentials as a dictionary"""
        cls.validate()
        return {
            'client_id': cls.CLIENT_ID,
            'client_secret': cls.CLIENT_SECRET,
            'user_agent': cls.USER_AGENT
        }
