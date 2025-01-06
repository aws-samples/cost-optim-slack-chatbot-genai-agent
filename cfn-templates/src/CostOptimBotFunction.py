import json
import boto3
import urllib3
import os
import logging

# Initialize the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Bedrock client used to interact with APIs around models
http = urllib3.PoolManager()
# Bedrock Runtime client used to invoke and question the models
bedrock_runtime = boto3.client(
    service_name="bedrock-agent-runtime", region_name=os.environ.get("Region")
)
slackUrl = "https://slack.com/api/chat.postMessage"
slackToken = os.environ.get("token")


def validate_slack_event(slack_event):
    """
    Validates the incoming Slack event to ensure it contains the required
    properties.

    Args:
        slack_event (dict): The Slack event data.

    Returns:
        bool: True if the Slack event is valid, False otherwise.
    """
    required_properties = [
        "type",
        "event.text",
        "event.user",
        "event.channel",
        "event.client_msg_id",
    ]

    for prop in required_properties:
        if prop not in slack_event:
            logger.error(f"Missing required property: {prop}")
            return False

    return True


def lambda_handler(event, context):
    """
    Lambda function handler.

    Args:
        event (dict): The event data received by the Lambda function.
        context (object): The context object for the Lambda function.
    """
    try:
        logger.info("## EVENT")
        logger.info(event)

        # Parse the incoming event
        slack_body = json.loads(event["body"])

        # Handle the URL verification event
        if slack_body["type"] == "url_verification":
            return {"statusCode": 200, "body": json.dumps(slack_body)}

        # Extract relevant data from the Slack event
        slack_text = slack_body.get("event").get("text")
        slack_user = slack_body.get("event").get("user")
        channel = slack_body.get("event").get("channel")
        client_msg_id = slack_body.get("event").get("client_msg_id")
        bot_id = slack_body.get("event").get("bot_id")

        logger.info(
            "Slack Txt: {}, User: {}, Client MsgID: {}, BotID: {}".format(
                slack_text, slack_user, client_msg_id, bot_id
            )
        )

        # Ignore messages from bots
        if bot_id is not None:
            logger.info("Ignoring message from bot")
            return {"statusCode": 200, "body": json.dumps({"msg": "msg rcvd"})}

        # Check if the DynamoDB table exists, and create it if necessary
        dydb = boto3.resource("dynamodb", region_name=os.environ.get("Region"))
        table_name = os.environ.get("TableName")
        try:
            table = dydb.Table(table_name)
            table.load()
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Internal Server Error"}),
            }

        # Check if the message has already been processed
        msg_exists = table.get_item(Key={"eventid": client_msg_id})

        if msg_exists.get("Item") is not None:
            logger.info(f"Msg already processed :" f"{msg_exists.get('Item')}")
            return {"statusCode": 200, "body": json.dumps({"msg": "msg rcvd"})}

        # Invoke the Bedrock agent
        response = bedrock_runtime.invoke_agent(
            agentId=os.environ.get("BedrockAgentId"),
            agentAliasId=os.environ.get("BedrockAliasId"),
            sessionId=client_msg_id,
            inputText=slack_text,
        )

        # Process and concatenate the response from the agent
        completion = ""
        for event in response.get("completion"):
            chunk = event["chunk"]
            completion += chunk["bytes"].decode()
            logger.info(f"Agent Response: {completion}")

        # Post the agent's response to Slack
        data = {"channel": channel, "text": completion}
        response = http.request(
            "POST",
            slackUrl,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {slackToken}",
            },
            body=json.dumps(data),
        )

        logger.info(f"Slack Response: {response.data}")

        # Store the message ID in DynamoDB
        table.put_item(Item={"eventid": client_msg_id})

        return {"statusCode": 200, "body": json.dumps({"msg": "msg rcvd"})}

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Internal Server Error"}),
        }
