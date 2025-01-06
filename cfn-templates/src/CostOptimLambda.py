import json
import os
import logging

# Initialize the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


# Function to validate and sanitize input
def validate_input(input_text):
    """
    Validates and sanitizes the input text to prevent
    potential security vulnerabilities.

    Args:
        input_text (str): The input text to validate and sanitize.

    Returns:
        str: The sanitized input text.
    """
    # Remove any potentially dangerous characters or patterns from the input
    sanitized_input = input_text.replace("<", "&lt;").replace(">", "&gt;")

    return sanitized_input


def format_response(
    action_group,
    api_path,
    http_method,
    http_status_code,
    dashboard_url,
    content_type="text/html",
    session_attributes=None,
    prompt_session_attributes=None,
):
    """
    Formats the response according to the specified message format.

    Args:
        action_group (str): The action group of the response.
        api_path (str): The API path requested.
        http_method (str): The HTTP method used for the request.
        http_status_code (int): The HTTP status code to return.
        dashboard_url (str): The body of the response (dashboard url).
        content_type (str): The content type of the response body.
        session_attributes (dict): Contains session attributes
        and their values.
        prompt_session_attributes (dict): Contains prompt attributes
        and their values.

    Returns:
        dict: The formatted response.
    """
    if session_attributes is None:
        session_attributes = {}
    if prompt_session_attributes is None:
        prompt_session_attributes = {}
    # Convert JSON string if it's not already a string
    if isinstance(dashboard_url, dict):
        dashboard_url = json.dumps(dashboard_url)
    return {
        "messageVersion": "1.0",
        "response": {
            "actionGroup": action_group,
            "apiPath": api_path,
            "httpMethod": http_method,
            "httpStatusCode": http_status_code,
            "responseBody": {content_type: {"url": dashboard_url}},
            "sessionAttributes": session_attributes,
            "promptSessionAttributes": prompt_session_attributes,
        },
    }


def lambda_handler(event, context):
    """
    Lambda function handler.

    Args:
        event (dict): The event data received by the Lambda function.
        context (object): The context object for the Lambda function.

    Returns:
        dict: The response to be returned by the Lambda function.
    """
    try:
        # Log the event and context
        logger.info("## EVENT")
        logger.info(event)
        logger.info("## CONTEXT")
        logger.info(context)

        # Validate and sanitize the input text
        input_text = event.get("inputText", "")
        sanitized_input = validate_input(input_text)
        logger.info(f"## INPUT TEXT: {sanitized_input.lower()}")

        dashboard_url = (
            "https://"
            + os.environ["AWS_REGION"]
            + ".quicksight.aws.amazon.com/sn/dashboards/cudos-v5/"
        )

        logger.info(f"## DASHBOARD URL: {dashboard_url}")

        # Extract the required parameters from the event
        api_path = event["apiPath"]
        logger.info(f"API Path: {api_path}")
        action_group = event.get("actionGroup", "defaultGroup")
        http_method = event.get("httpMethod", "GET")
        session_attributes = {}  # not implemented at this point
        prompt_session_attributes = {}  # not implemented at this point

        # Format the response
        formatted_response = format_response(
            action_group,
            api_path,
            http_method,
            200,
            dashboard_url,
            session_attributes=session_attributes,
            prompt_session_attributes=prompt_session_attributes,
        )
        logger.info(f"Formatted response: {formatted_response}")

        return formatted_response

    except Exception as e:
        logger.error(f"Error: {e}")
        return {
            "statusCode": 500,
            "body": "Error getting QuickSight dashboard embed URL",
        }
