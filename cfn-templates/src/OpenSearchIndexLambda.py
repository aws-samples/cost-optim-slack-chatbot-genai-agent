from urllib.request import Request, urlopen
import boto3
import json
import asyncio
import logging
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

# Initialize the logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)


def send_response(
    event,
    context,
    responseStatus,
    responseData,
    physicalResourceId=None,
    noEcho=False,
):
    """
    Sends a response to the CloudFormation service with the specified
    status and data.

    Args:
        event (dict): The event data received by the Lambda function.
        context (object): The context object for the Lambda function.
        responseStatus (str): The status of the response (e.g., "SUCCESS"..).
        responseData (dict): The data to be included in the response.
        physicalResourceId (str, optional): Physical resourceID. Default=None.
        noEcho (bool, optional): Echo the response data. Default=False.
    """
    responseUrl = event["ResponseURL"]

    responseBody = {}
    responseBody["Status"] = responseStatus
    responseBody["Reason"] = (
        "See the details in CloudWatch Log Stream: " + context.log_stream_name
    )
    responseBody["PhysicalResourceId"] = (
        physicalResourceId or context.log_stream_name
    )
    responseBody["StackId"] = event["StackId"]
    responseBody["RequestId"] = event["RequestId"]
    responseBody["LogicalResourceId"] = event["LogicalResourceId"]
    responseBody["NoEcho"] = noEcho
    responseBody["Data"] = responseData

    json_responseBody = json.dumps(responseBody)

    headers = {
        "content-type": "",
        "content-length": str(len(json_responseBody)),
    }

    try:
        req = Request(
            responseUrl,
            data=json_responseBody.encode("utf-8"),
            headers=headers,
            method="PUT",
        )
        if req.full_url.lower().startswith("http"):
            # amazonq-ignore-next-line
            response = urlopen(req)
        else:
            raise ValueError from None

        logger.info(f"Status code: {response.getcode()}")
        logger.info(f"Status message: {response.msg}")
    except Exception as e:
        logger.error(
            f"send(..) failed executing request.urlopen(..): {str(e)}"
        )


async def create_index_with_retry(
    client, index_name, index_body, max_retries=5, base_delay=5
):
    """
    Attempts to create an OpenSearch index with retry logic.

    Args:
        client (OpenSearch): The OpenSearch client instance.
        index_name (str): The name of the index to create.
        index_body (dict): The configuration for the index.
        max_retries (int, optional): The max nb of retries. Default=5.
        base_delay (int, optional): Base delay (sec) btween retries. Default=5.

    Returns:
        bool: True if the index was created successfully, False otherwise.
    """
    # Initial delay before attempting to create the index
    logger.info("Waiting 50 seconds before attempting to create the index...")
    await asyncio.sleep(50)

    for attempt in range(max_retries):
        try:
            response = client.indices.create(
                index=index_name, body=json.dumps(index_body)
            )
            logger.info(f"Index created: {response}")
            logger.info(
                "Waiting 60 seconds for the index to be fully created..."
            )
            await asyncio.sleep(60)
            return True
        except Exception as e:
            logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                delay = base_delay * (2**attempt)  # Exponential backoff
                logger.info(f"Retrying in {delay} seconds...")
                await asyncio.sleep(delay)
            else:
                logger.error("Max retries reached. Index creation failed.")
                return False


def validate_input(event):
    """
    Check input event data to contain the required properties.

    Args:
        event (dict): The event data received by the Lambda function.

    Returns:
        bool: True if the input is valid, False otherwise.
    """
    collection_name = event["ResourceProperties"]["CollectionName"]
    index_name = event["ResourceProperties"]["IndexName"]
    collection_id = event["ResourceProperties"]["CollectionId"]
    region = event["ResourceProperties"]["Region"]

    logger.info(f"Collection Name: {collection_name}")
    logger.info(f"Index Name: {index_name}")
    logger.info(f"Collection ID: {collection_id}")
    logger.info(f"Region: {region}")

    prop = (
        (event["ResourceProperties"]["CollectionName"])
        and (event["ResourceProperties"]["IndexName"])
        and (event["ResourceProperties"]["CollectionId"])
        and (event["ResourceProperties"]["Region"])
    )

    if not prop:
        logger.error(f"Missing required property: {prop}")
        return False

    return True


def handler(event, context):
    """
    Lambda function handler.

    Args:
        event (dict): The event data received by the Lambda function.
        context (object): The context object for the Lambda function.
    """
    # Validate the input event data
    if not validate_input(event):
        send_response(event, context, "FAILED", {})
        return

    if event["RequestType"] in ["Create", "Update"]:
        try:
            collection_name = event["ResourceProperties"]["CollectionName"]
            index_name = event["ResourceProperties"]["IndexName"]
            collection_id = event["ResourceProperties"]["CollectionId"]
            region = event["ResourceProperties"]["Region"]

            logger.info(f"Collection Name: {collection_name}")
            logger.info(f"Index Name: {index_name}")
            logger.info(f"Collection ID: {collection_id}")
            logger.info(f"Region: {region}")

            service = "aoss"
            host = f"{collection_id}.{region}.{service}.amazonaws.com"
            credentials = boto3.Session().get_credentials()
            awsauth = AWSV4SignerAuth(credentials, region, service)

            client = OpenSearch(
                hosts=[{"host": host, "port": 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection,
                pool_maxsize=20,
            )

            # Updated index_body to match Amazon Titan model specifications
            index_body = {
                "settings": {
                    "index": {"knn": True, "knn.algo_param.ef_search": 512}
                },
                "mappings": {
                    "properties": {
                        "vector": {
                            "type": "knn_vector",
                            "dimension": 1024,
                            "method": {
                                "name": "hnsw",
                                "engine": "faiss",
                                "parameters": {
                                    "ef_construction": 512,
                                    "m": 16,
                                },
                                "space_type": "l2",
                            },
                        },
                    }
                },
            }

            # Attempt to create the index with retry logic
            if asyncio.run(
                create_index_with_retry(client, index_name, index_body)
            ):
                send_response(event, context, "SUCCESS", {})
            else:
                send_response(event, context, "FAILED", {})

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            send_response(event, context, "FAILED", {})
    else:
        send_response(event, context, "SUCCESS", {})
