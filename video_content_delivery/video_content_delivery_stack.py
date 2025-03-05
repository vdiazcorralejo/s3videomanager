from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_apigatewayv2 as apigwv2,
    aws_apigatewayv2_integrations as integrations,
    RemovalPolicy,
    CfnOutput,
    Duration,
)
from constructs import Construct
from video_content_delivery.lambda_construct import LambdaConstruct
from video_content_delivery.dynamo_table import DynamoTable

class VideoContentDeliveryStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

          # Crear la tabla DynamoDB usando la clase
        table_name = "listOfVideoFiles"
        video_table = DynamoTable(self, table_name)
        print(f"Table ARN: {video_table.table.table_arn}")
        print(f"Table NAME: {video_table.table.table_name}")

        bucket = s3.Bucket(self, "VideoBucket",
                           versioned=True,
                           bucket_name="video-content-delivery-bucket",
                           removal_policy=RemovalPolicy.DESTROY,
                           auto_delete_objects=True,
                           block_public_access=s3.BlockPublicAccess.BLOCK_ALL)
        
        environment_l = {
            "TABLE_NAME": table_name,
            "REGION": "eu-west-1",
            "BUCKET_NAME": bucket.bucket_name,
        }
        
        # Creamos las lambdas que vamos a usar
        get_presigned_url_function = LambdaConstruct(
            self,
            "MyCustomLambda1",
            handler_file="index.handler",
            path_l="video_content_delivery/src/lambda/generate_url_pre",
            function_name="GetPresignedUrlFunction",
            table=video_table,
            environment=environment_l
        )
        print(f"Lambda GetPresignedUrlFunction ARN: {get_presigned_url_function.lambda_function.function_arn}")

        bucket.grant_read_write(get_presigned_url_function.lambda_function)

        http_api = apigwv2.HttpApi(
            self, 
            "VideoApi",
            api_name="Video Service",
            cors_preflight={
                "allow_methods": [apigwv2.CorsHttpMethod.GET, apigwv2.CorsHttpMethod.PUT],
                "allow_origins": ['*'],
                "allow_headers": ['Content-Type'],
                "max_age": Duration.days(1)
            }
        )

        # Create Lambda integration
        lambda_integration = integrations.HttpLambdaIntegration(
            "PresignedUrlIntegration",
            get_presigned_url_function.lambda_function
        )

        # Add routes
        http_api.add_routes(
            path="/",
            methods=[apigwv2.HttpMethod.GET, apigwv2.HttpMethod.PUT],
            integration=lambda_integration
        )

        # Add API URL output
        CfnOutput(self, "HttpApiUrl", 
            value=http_api.url,
            description="HTTP API endpoint URL"
        )
