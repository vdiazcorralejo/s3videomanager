from aws_cdk import (
    aws_lambda as lambda_,
    aws_iam as iam,
    BundlingOptions,
    Stack)
from constructs import Construct
from video_content_delivery.dynamo_table import DynamoTable

class LambdaConstruct(Construct):
    def __init__(self, scope: Construct, id: str, handler_file: str, path_l: str, function_name: str,table: DynamoTable= None, environment: str=None, **kwargs):
        super().__init__(scope, id)
    
        self.lambda_function = lambda_.Function(
            self,
            "LambdaFunction",
            runtime=lambda_.Runtime.PYTHON_3_8,
            handler=f"{handler_file.split('.')[0]}.handler",
            code=lambda_.Code.from_asset(
                path=path_l),
            function_name=function_name,
            environment=environment,
            **kwargs
        )

        # Agregar permisos para DynamoDB
        if table:
            table.table.grant_full_access(self.lambda_function)
            print(f"Granted full access to DynamoDB table: {table.table.table_name}")
