# 
# For demo purposes only, not for use in production
#
import argparse
import boto3
import botocore
import json
import base64
from botocore.exceptions import ClientError

def invoke_nova_pro(aws_region, prompt, base64_image_data, metric_text, config_output, xray_output):
    """
    Invokes Amazon Nova Pro to run a multimodal inference using the input
    provided in the request body.
    """

    print("Calling Amazon Bedrock API ...")

    # Initialize the Amazon Bedrock runtime client
    client = boto3.client(
        service_name="bedrock-runtime", region_name=aws_region
    )

    # Invoke the model with the prompt, encoded image, and metrics file
    model_id = "arn:aws:bedrock:us-west-2:12345678911:inference-profile/us.amazon.nova-pro-v1:0"  # Use your inference profile ARN
    request_body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "text": prompt
                    },
                    {
                        "image": {
                            "format": "png",
                            "source": {
                                "bytes": base64_image_data
                            }
                        }
                    },
                    {
                        "text": metric_text
                    },
                    {
                        "text": config_output
                    },
                    {
                        "text": xray_output
                    }
                ]
            }
        ],
        "inferenceConfig": {
            "maxTokens": 2048,
            "temperature": 0.0,
            "topP": 1.0
        }
    }

    try:
        response = client.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body)
        )

        # Process and print the response
        result = json.loads(response.get("body").read())
        
        # Extract response metadata
        response_metadata = response.get("ResponseMetadata", {})
        
        print("Invocation details:")
        # Print token usage from response metadata
        if "x-amzn-bedrock-input-token-count" in response_metadata.get("HTTPHeaders", {}):
            print(f"- Input tokens: {response_metadata['HTTPHeaders']['x-amzn-bedrock-input-token-count']}")
        else:
            print("- Input tokens: N/A")
            
        if "x-amzn-bedrock-output-token-count" in response_metadata.get("HTTPHeaders", {}):
            print(f"- Output tokens: {response_metadata['HTTPHeaders']['x-amzn-bedrock-output-token-count']}")
        else:
            print("- Output tokens: N/A")

        # Print model response
        output_message = result.get("output", {}).get("message", {})
        if output_message and "content" in output_message:
            print("\nModel Response:")
            for content in output_message["content"]:
                if "text" in content:
                    print(content["text"])

        return result

    except ClientError as err:
        print(
            f"Couldn't invoke Nova Pro. Here's why: {err.response['Error']['Code']}: "
            f"{err.response['Error']['Message']}"
        )
        raise

if __name__ == "__main__":
    # Create object for required args
    parser = argparse.ArgumentParser(description='This script calls the Amazon Bedrock API.')
    parser.add_argument('aws_region', help='AWS region for Bedrock API, such as us-east-1.')
    parser.add_argument('s3_bucket', help='S3 bucket holding observability data')
    args = parser.parse_args()

    # Creating an S3 access object
    s3 = boto3.resource('s3')

    # Download the ALB metrics, AWS Config output, and X-Ray output from S3
    print("Downloading files from S3 ...")

    key = ["alb.csv", "aws_config_output.txt", "xray_output.txt", "app_diagram.png"]
    for filename in key:
        try:
            s3.Bucket(args.s3_bucket).download_file(filename, 'XX' + filename)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == "404":
                print("The object " + filename + " does not exist.")
            else:
                raise

    # Read the ALB metric output
    with open('alb.csv', 'r', encoding="utf-8") as f:
        alb_metrics = f.read()

    # Read the AWS Config output
    with open('aws_config_output.txt', 'r', encoding="utf-8") as f:
        config_output = f.read()

    # Read the AWS X-Ray output
    with open('xray_output.txt', 'r', encoding="utf-8") as f:
        xray_output = f.read()

    # Convert image to base64 
    image_path = "./app_diagram.png"
    with open(image_path, "rb") as image_file:
        image = base64.b64encode(image_file.read()).decode("utf8")

    prompt = (
        "Document 1: AWS services and workflow for an application are shown in the architecture diagram\n{{image}}\n\n"
        "Document 2: ALB CloudWatch metrics are in\n{{alb_metrics}}\n\n"
        "Document 3: AWS Config data is in\n{{config_output}}\n\n"
        "Document 4: AWS X-Ray data is in\n{{xray_output}}\n\n"
        "The application is experiencing a problem. Clients are unable to access the frontend website.\n\n"
        "Based on Document 1, Document 2, Document 3, and Document 4, identify likely causes of the issue and rank them by probability.\n\n"
        "Examine Document 3 and determine if any configurationItems changes have been made. If a change has been made, list the specific resource, such as resourceId and the details of the recent change including configuration and ipPermissions.\n\n"
        "Recommend troubleshooting steps and actions using specific AWS services that are found in Document 1. Provide a detailed explanation.\n\n"
        "Provide wording to use to communicate the issue on the company's social media. The social media wording should use the persona of Disney's Chip & Dale characters and be gender neutral and appropriate for children. Follow all COPPA rules.\n\n"
        "The Chip & Dale persona should be used only for the social media suggested message.\n\n"
    )

    invoke_nova_pro(args.aws_region, prompt, image, alb_metrics, config_output, xray_output)