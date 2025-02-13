#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import requests
import json
import sys
import os
import logging
from logging.handlers import RotatingFileHandler

# Configure logging with rotation
log_file_path = 'smseagle.log'
log_max_size = 2 * 1024 * 1024  # 2MB
log_backup_count = 5  # Keep 5 backup logs

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = RotatingFileHandler(log_file_path, maxBytes=log_max_size, backupCount=log_backup_count)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

def load_configuration(path):
    """Loads the configuration from the JSON file."""
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError:
        logger.error(f"Error reading the configuration file: {path}")
        sys.exit(1)

def send_message(url, payload, headers, disable_ssl=False):
    """Sends a message to the SMS Eagle API and logs all responses."""
    response = None  # Initialize response to None
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), verify=False)
        response.raise_for_status()
        try:  # Nested try-except for JSON decoding
            response_data = response.json()
            logger.info(f"API Response: {response_data}")  # Log the full response

            if isinstance(response_data, list):  # Check if it's a list
                logger.error("API returned a list, not a dictionary as expected.") # Log if it's a list
                return False, None # Return failure
            elif isinstance(response_data, dict) and response_data.get("status") == "queued": # isinstance check
                logger.info(f"Message sent successfully. Number: {response_data.get('number')}, ID: {response_data.get('id')}")
                return True, response_data
            elif isinstance(response_data, dict): # isinstance check
                logger.error(f"Error sending message: {response_data.get('message')}. Status Code: {response.status_code}. Response: {response.text}")  # More details
                return False, response_data
            else: # if it's neither dict nor list
                logger.error(f"Unexpected API response type: {type(response_data)}. Response: {response.text}")
                return False, None

        except json.JSONDecodeError: # Catch the JSON error
            logger.error(f"Invalid JSON response: {response.text}")
            return False, None

    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {e}. Response: {response.text if response is not None and hasattr(response, 'text') else 'No response text available'}")  # More details
        return False, None

def send_message_type(message_type, target, text=None, wave_id=None, disable_ssl=False, **kwargs):
    """Generic function to send different message types (SMS, TTS, Wave)."""
    target.update({"modem_no": kwargs.get("modem_no", 2)})

    if message_type == "sms":
        target.update({"text": text})
        url = url_sms
    elif message_type == "call_tts":
        target.update({"text": text, "voice_id": 3})
        url = url_call_tts
    elif message_type == "wave":
        target.update({"wave_id": wave_id})
        url = url_wave
    else:
        logger.error(f"Invalid message type: {message_type}")
        return False, None

    success, data = send_message(url, target, headers, disable_ssl)

    if not success:
        logger.info("Trying second server...")
        alternative_url = url.replace(config['smseagleip1'], config['smseagleip2'])
        alternative_headers = {'Content-Type': 'application/json', 'access-token': config['access-token2']}
        success, data = send_message(alternative_url, target, alternative_headers, disable_ssl)

    return success, data

def print_help():
    """Prints the help message."""
    help_text = """
    Usage:
        python smseagle_v2.py <type> [--to <number>] [--contacts <id1,id2,...>] [--groups <id1,id2,...>] [--text <message>] [--wave-id <id>] [--modem_no <number>] [--disable-ssl]

    Parameters:
        type         - Required. Type of message: sms, call_tts, or wave.
        --to           - Optional. Phone number for the message.
        --contacts     - Optional. Contact IDs for the message.
        --groups       - Optional. Group IDs for the message.
        --text         - Required for sms and call_tts. Text of the message.
        --wave-id      - Required for wave. ID of the WAV file.
        --modem_no     - Optional. Modem number. Default is 2.
        --disable-ssl - Optional. Disables SSL certificate verification (insecure!).

    Examples:
        # Send SMS to number and group (SSL enabled)
        python smseagle_v2.py sms --to +49123456789 --groups 1,2 --text "Hello World" --modem_no 1

        # Send TTS call to contacts and group (SSL disabled)
        python smseagle_v2.py call_tts --contacts 12,15 --groups 3 --text "This is a test." --modem_no 1 --disable_ssl

        # Send Wave call (SSL enabled)
        python smseagle_v2.py wave --groups 57,35 --wave-id 2 --modem_no 1
    """
    print(help_text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Send SMS, TTS, or Wave messages via SMS Eagle API.")

    parser.add_argument("type", help="Type of message: sms, call_tts, or wave")
    parser.add_argument("--to", help="Phone number for the message")
    parser.add_argument("--contacts", help="Contact IDs for the message (comma-separated)")
    parser.add_argument("--groups", help="Group IDs for the message (comma-separated)")
    parser.add_argument("--text", help="Text of the message (required for sms and call_tts)")
    parser.add_argument("--wave-id", type=int, help="ID of the WAV file (required for wave)")  # Use hyphen consistently
    parser.add_argument("--modem_no", type=int, default=2, help="Modem number (default: 2)")
    parser.add_argument("--disable_ssl", action="store_true", help="Disable SSL certificate verification (insecure!)")

    args = parser.parse_args()

    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    config = load_configuration(config_path)

    # API endpoints and tokens from the configuration
    url_sms = f"{config['smseagleip1']}/api/v2/messages/sms"
    url_call_tts = f"{config['smseagleip1']}/api/v2/calls/tts_advanced"
    url_wave = f"{config['smseagleip1']}/api/v2/calls/wave"
    access_token = config['access-token1']

    headers = {
        'Content-Type': 'application/json',
        'access-token': access_token
    }

    action = args.type
    text = args.text
    wave_id = args.wave_id
    modem_no = args.modem_no
    disable_ssl = args.disable_ssl
    target = {"modem_no": modem_no}

    # Add recipients (combination of to, contacts, and groups)
    if args.to:
        target["to"] = [args.to]
    if args.contacts:
        target["contacts"] = [int(id) for id in args.contacts.split(",")]
    if args.groups:
        target["groups"] = [int(id) for id in args.groups.split(",")]

    # Check if at least one recipient is specified
    if not (target.get("to") or target.get("contacts") or target.get("groups")):
        print("""Error: At least one of the parameters 'to', 'contacts', or 'groups' is required.""")
        sys.exit(1)

    if action == "sms":
        if not text:
            print("Error: The 'text' parameter is required for SMS messages.")
            sys.exit(1)
        success, data = send_message_type("sms", target, text=text, modem_no=modem_no, disable_ssl=disable_ssl)
    elif action == "call_tts":  # Correct indentation (4 spaces)
        if not text:          # Correct indentation (8 spaces)
            print("Error: The 'text' parameter is required for TTS calls.")
            sys.exit(1)      # Correct indentation (8 spaces)
        success, data = send_message_type("call_tts", target, text=text, modem_no=modem_no, disable_ssl=disable_ssl)
    elif action == "wave":      # Correct indentation (4 spaces)
        if not wave_id:      # Correct indentation (8 spaces)
            print("Error: The 'wave_id' parameter is required for Wave calls.")
            sys.exit(1)      # Correct indentation (8 spaces)
        success, data = send_message_type("wave", target, wave_id=wave_id, modem_no=modem_no, disable_ssl=disable_ssl)
    else:                  # Correct indentation (4 spaces)
        print("Invalid action. Use 'sms', 'call_tts', or 'wave'.") # Correct indentation (8 spaces)
        sys.exit(1)          # Correct indentation (8 spaces)

    if success:          # Correct indentation (4 spaces)
        logger.info("Action performed successfully.")  # Log success
        # print(data)  # For debugging: print complete data
    else:                  # Correct indentation (4 spaces)
        logger.error("Action failed.")  # Log failure
        # print(data)  # For debugging: print complete data
