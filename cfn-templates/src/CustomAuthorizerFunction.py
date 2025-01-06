import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    logger.info("Received event: {}".format(event))
    # Custom authorization logic has been disabled for now
    # All requests are allowed through the custom authorizer

    # For this example, we'll just allow all requests
    auth_response = {
        "principalId": "user",
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": event["methodArn"],
                }
            ],
        },
    }

    logger.info("Returning auth response: {}".format(auth_response))
    return auth_response
