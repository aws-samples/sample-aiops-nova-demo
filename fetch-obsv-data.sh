#!/bin/sh

# For demo purposes only.  Not for use in production.
#
#
# Fetch CloudWatch ALB metrics, AWS Config data, X-Ray trace data
# for further analysis by Bedrock

# Check if the required number of arguments is provided
if [ $# -ne 2 ]; then
    echo "Usage: $0 <AWS region for CloudWatch metrics> <S3 bucket name>"
    exit 1
fi

# Access the arguments
CW_METRIC_REGION="$1"
S3_BUCKET="$2"

# Check to ensure S3 bucket exists
if ! aws s3api head-bucket --bucket "$S3_BUCKET" >/dev/null 2>&1; then
    echo "Error: S3 bucket $S3_BUCKET does not exist."
    exit 1
fi

EPOCH=$(date +%s)
echo "Creating temp directory to hold downloads ..."
TMPDIR=$(mktemp -d)
echo "Temporary directory created: $TMPDIR"
echo

#
# Fetch CloudWatch ALB metric data
# timeframe (period/hours) is specified in metrics.yaml
# output is saved to alb.csv in local directory
#
echo "Fetching Amazon CloudWatch ALB metrics for the past 30 min ..."
python3 cwreport.py alb --region $CW_METRIC_REGION > /dev/null
mv "./alb.csv" $TMPDIR"/alb.csv"

echo 

# Fetch AWS Config data
# timeframe is data from the past 30 min
# output is saved to aws_config_output.txt in local directory
#
echo "Fetching AWS Config data for the past 30 min ..."

if [ -f "aws_config_output.txt" ]; then /bin/rm "aws_config_output.txt"; fi

for resourceId in `aws configservice list-discovered-resources --resource-type AWS::EC2::SecurityGroup | jq -r '.resourceIdentifiers[].resourceId'`; do
    aws configservice get-resource-config-history --resource-type AWS::EC2::SecurityGroup --resource-id "$resourceId" --earlier-time $(($EPOCH-1800)) >> $TMPDIR"/aws_config_output.txt"
done

echo 

# Fetch X-Ray trace data
# timeframe is data from the past 10 minutes
# output is saved to xray_output.txt in local directory
#
echo "Fetching AWS X-Ray data for the past 10 min ..."
aws xray get-service-graph --start-time $(($EPOCH-600)) --end-time $EPOCH > $TMPDIR"/xray_output.txt"

# upload output files to S3
for FILE_PATH in "$TMPDIR"/*;
    do
        FILENAME=$(basename "$FILE_PATH")
        aws s3 cp "$FILE_PATH" s3://"$S3_BUCKET"

        # Check for success
        if [ $? -eq 0 ]; then
            echo "File \"$FILENAME\" uploaded successfully to S3"
        else
            echo "Error uploading file to S3"
            exit 1
        fi
        echo 
    done

exit 0
