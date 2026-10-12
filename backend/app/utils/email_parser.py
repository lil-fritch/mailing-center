"""
Email parsing utilities for cleaning up reply content.
"""

from email_reply_parser import EmailReplyParser
import email.header


def decode_email_header(header: str) -> str:
    """
    Decode MIME encoded-word format in email headers.
    
    Args:
        header: The encoded header string
        
    Returns:
        Decoded header string
    """
    if not header:
        return header
    
    try:
        decoded_parts = email.header.decode_header(header)
        decoded_string = ""
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                if encoding:
                    decoded_string += part.decode(encoding)
                else:
                    decoded_string += part.decode('utf-8', errors='ignore')
            else:
                decoded_string += part
        return decoded_string
    except Exception:
        # If decoding fails, return original string
        return header


def clean_reply_body(body: str) -> str:
    """
    Clean reply body by removing the original email content using email-reply-parser.
    
    Args:
        body: The raw email body containing both reply and original content
        
    Returns:
        Cleaned reply body with only the new reply content
    """
    if not body:
        return body
    
    try:
        # Use the email-reply-parser library to extract only the reply
        clean_reply = EmailReplyParser.parse_reply(body)
        return clean_reply.strip()
    except Exception:
        # Fallback to original body if parsing fails
        return body.strip()