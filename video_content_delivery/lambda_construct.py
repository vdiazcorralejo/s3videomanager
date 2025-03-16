from aws_cdk import (
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_iam as iam,
    BundlingOptions,
    Stack,
    RemovalPolicy
)
from constructs import Construct
from video_content_delivery.dynamo_table import DynamoTable

class LambdaConstruct(Construct):
    def __init__(self, scope: Construct, id: str, handler_file: str, path_l: str, 
                 function_name: str, runtime: lambda_.Runtime, table: DynamoTable = None, 
                 environment: dict = None, **kwargs):
        super().__init__(scope, id)
    
        # Create the Lambda function
        self.lambda_function = lambda_.Function(
            self,
            "LambdaFunction",
            runtime=runtime,
            handler=f"{handler_file.split('.')[0]}.handler",
            code=lambda_.Code.from_asset(path=path_l),
            function_name=function_name,
            environment=environment,
            **kwargs
        )

        # Create CloudWatch Log Group
        log_group = logs.LogGroup(
            self,
            f"{function_name}LogGroup",
            log_group_name=f"/aws/lambda/{function_name}",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Grant permissions to Lambda to write logs
        log_group.grant_write(self.lambda_function)

        # Add DynamoDB permissions if table is provided
        if table:
            table.table.grant_full_access(self.lambda_function)
            print(f"LambdaConstruct(): Granted full access to DynamoDB table: {table.table.table_name}")
