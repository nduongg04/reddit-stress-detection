"""
Reddit data schema transformations and validation
"""
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


def transform_submission(submission):
    """
    Transform PRAW submission to standardized format

    Args:
        submission: PRAW Submission object

    Returns:
        dict: Standardized post data
    """
    try:
        return {
            "post_id": submission.id,
            "title": submission.title,
            "body": submission.selftext or "",  # Some submissions have no body
            "author": submission.author.name if submission.author else "[deleted]",
            "subreddit": submission.subreddit.display_name,
            "created_utc": int(submission.created_utc),
            "score": submission.score,
            "num_comments": submission.num_comments,
            "url": submission.url,
            "permalink": f"https://reddit.com{submission.permalink}",
            "type": "submission",
            "source": "praw",
            "ingestion_timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error transforming submission {submission.id}: {e}")
        raise


def transform_comment(comment):
    """
    Transform PRAW comment to standardized format

    Args:
        comment: PRAW Comment object

    Returns:
        dict: Standardized post data
    """
    try:
        return {
            "post_id": comment.id,
            "title": "",  # Comments don't have titles
            "body": comment.body,
            "author": comment.author.name if comment.author else "[deleted]",
            "subreddit": comment.subreddit.display_name,
            "created_utc": int(comment.created_utc),
            "score": comment.score,
            "parent_id": comment.parent_id,
            "link_id": comment.link_id,
            "permalink": f"https://reddit.com{comment.permalink}",
            "type": "comment",
            "source": "praw",
            "ingestion_timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error transforming comment {comment.id}: {e}")
        raise


def validate_post(post_dict):
    """
    Validate post has required fields

    Args:
        post_dict: Post data dictionary

    Returns:
        bool: True if valid, False otherwise
    """
    required_fields = ['post_id', 'body', 'author', 'subreddit', 'created_utc', 'type', 'source']

    for field in required_fields:
        if field not in post_dict:
            logger.warning(f"Post validation failed: missing field '{field}'")
            return False

    # Validate post_id is not empty
    if not post_dict.get('post_id'):
        logger.warning("Post validation failed: post_id is empty")
        return False

    # Validate type is either 'submission' or 'comment'
    if post_dict.get('type') not in ['submission', 'comment']:
        logger.warning(f"Post validation failed: invalid type '{post_dict.get('type')}'")
        return False

    # For submissions, body can be empty but title should not be
    if post_dict.get('type') == 'submission' and not post_dict.get('title'):
        logger.warning("Submission validation failed: title is empty")
        return False

    # For comments, body should not be empty
    if post_dict.get('type') == 'comment' and not post_dict.get('body'):
        logger.warning("Comment validation failed: body is empty")
        return False

    return True


def sanitize_text(text, max_length=10000):
    """
    Sanitize text content

    Args:
        text: Text to sanitize
        max_length: Maximum text length

    Returns:
        str: Sanitized text
    """
    if not text:
        return ""

    # Remove null bytes
    text = text.replace('\x00', '')

    # Truncate if too long
    if len(text) > max_length:
        logger.warning(f"Text truncated from {len(text)} to {max_length} characters")
        text = text[:max_length] + "... [truncated]"

    return text


def serialize_post(post_dict):
    """
    Serialize post to JSON string

    Args:
        post_dict: Post data dictionary

    Returns:
        str: JSON string
    """
    try:
        return json.dumps(post_dict)
    except Exception as e:
        logger.error(f"Error serializing post: {e}")
        raise


def deserialize_post(json_str):
    """
    Deserialize JSON string to post dictionary

    Args:
        json_str: JSON string

    Returns:
        dict: Post data dictionary
    """
    try:
        return json.loads(json_str)
    except Exception as e:
        logger.error(f"Error deserializing post: {e}")
        raise
