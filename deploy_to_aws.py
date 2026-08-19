import os
import sys
import json
import time
import subprocess

AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-1")  # Mumbai region

env = os.environ.copy()
if AWS_ACCESS_KEY_ID:
    env["AWS_ACCESS_KEY_ID"] = AWS_ACCESS_KEY_ID
if AWS_SECRET_ACCESS_KEY:
    env["AWS_SECRET_ACCESS_KEY"] = AWS_SECRET_ACCESS_KEY
env["AWS_DEFAULT_REGION"] = AWS_REGION
aws_bin = os.path.expanduser("~/.local/bin/aws")

def run_aws(cmd_args):
    full_cmd = [aws_bin] + cmd_args
    print(f"Running: {' '.join(full_cmd)}")
    result = subprocess.run(full_cmd, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        print(f"Error ({result.returncode}): {result.stderr.strip()}")
    return result

def deploy():
    print("=== Step 1: Getting AWS Account Info ===")
    res = run_aws(["sts", "get-caller-identity", "--output", "json"])
    if res.returncode != 0:
        print("Failed to authenticate with AWS credentials.")
        sys.exit(1)
    
    identity = json.loads(res.stdout)
    account_id = identity["Account"]
    print(f"Account ID: {account_id}")
    print(f"Region: {AWS_REGION}")

    role_name = "flask_market_lambda_role"
    role_arn = f"arn:aws:iam::{account_id}:role/{role_name}"

    print("=== Step 2: Ensuring IAM Execution Role ===")
    # Check if role exists
    res = run_aws(["iam", "get-role", "--role-name", role_name, "--output", "json"])
    if res.returncode != 0:
        print(f"Creating IAM role {role_name}...")
        trust_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"Service": "lambda.amazonaws.com"},
                    "Action": "sts:AssumeRole"
                }
            ]
        }
        res = run_aws(["iam", "create-role", "--role-name", role_name, "--assume-role-policy-document", json.dumps(trust_policy)])
        run_aws(["iam", "attach-role-policy", "--role-name", role_name, "--policy-arn", "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"])
        print("Waiting 10 seconds for IAM role propagation...")
        time.sleep(10)

    function_name = "flask-market-app"
    zip_path = "function.zip"
    if not os.path.exists(zip_path):
        print(f"Error: {zip_path} not found in current directory.")
        sys.exit(1)

    print("=== Step 3: Deploying Lambda Function ===")
    res = run_aws(["lambda", "get-function", "--function-name", function_name, "--output", "json"])
    if res.returncode == 0:
        print(f"Updating code for existing function {function_name}...")
        run_aws(["lambda", "update-function-code", "--function-name", function_name, "--zip-file", f"fileb://{zip_path}"])
        print("Waiting 5 seconds for Lambda function state update...")
        time.sleep(5)
        run_aws(["lambda", "update-function-configuration", "--function-name", function_name, "--handler", "app.handler", "--runtime", "python3.11", "--timeout", "15", "--memory-size", "256", "--environment", "Variables={STRIP_STAGE_PATH=true}"])
    else:
        print(f"Creating new Lambda function {function_name}...")
        create_res = run_aws([
            "lambda", "create-function",
            "--function-name", function_name,
            "--runtime", "python3.11",
            "--role", role_arn,
            "--handler", "app.handler",
            "--zip-file", f"fileb://{zip_path}",
            "--timeout", "15",
            "--memory-size", "256",
            "--environment", "Variables={STRIP_STAGE_PATH=true}"
        ])
        if create_res.returncode != 0:
            print("Retrying create-function after extra IAM propagation delay...")
            time.sleep(10)
            run_aws([
                "lambda", "create-function",
                "--function-name", function_name,
                "--runtime", "python3.11",
                "--role", role_arn,
                "--handler", "app.handler",
                "--zip-file", f"fileb://{zip_path}",
                "--timeout", "15",
                "--memory-size", "256"
            ])

    # Get function ARN
    res = run_aws(["lambda", "get-function", "--function-name", function_name, "--output", "json"])
    func_info = json.loads(res.stdout)
    func_arn = func_info["Configuration"]["FunctionArn"]
    print(f"Lambda Function ARN: {func_arn}")

    print("=== Step 4: Configuring API Gateway (HTTP API) ===")
    api_name = "flask-market-api"
    api_id = None
    
    # Check existing APIs
    res = run_aws(["apigatewayv2", "get-apis", "--output", "json"])
    if res.returncode == 0:
        apis = json.loads(res.stdout).get("Items", [])
        for item in apis:
            if item.get("Name") == api_name:
                api_id = item.get("ApiId")
                break
    
    if not api_id:
        print("Creating HTTP API...")
        res = run_aws(["apigatewayv2", "create-api", "--name", api_name, "--protocol-type", "HTTP", "--target", func_arn, "--output", "json"])
        if res.returncode == 0:
            api_info = json.loads(res.stdout)
            api_id = api_info["ApiId"]

    endpoint_url = f"https://{api_id}.execute-api.{AWS_REGION}.amazonaws.com"
    print(f"API Gateway ID: {api_id}")

    print("=== Step 5: Granting API Gateway Permission to Invoke Lambda ===")
    statement_id = "apigateway-flask-market-permission"
    # Remove existing permission if present
    run_aws(["lambda", "remove-permission", "--function-name", function_name, "--statement-id", statement_id])
    run_aws([
        "lambda", "add-permission",
        "--function-name", function_name,
        "--statement-id", statement_id,
        "--action", "lambda:InvokeFunction",
        "--principal", "apigateway.amazonaws.com",
        "--source-arn", f"arn:aws:execute-api:{AWS_REGION}:{account_id}:{api_id}/*/*"
    ])

    print("\n========================================================")
    print("SUCCESS! Your Flask application is LIVE on AWS Lambda!")
    print(f"URL: {endpoint_url}")
    print("========================================================\n")

if __name__ == "__main__":
    deploy()
