from email.mime import audio
import json
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_logs as logs,  # Add this import
    aws_s3_notifications as s3n,  # Add this import
    RemovalPolicy,
    CfnOutput,
    Duration,
)
from constructs import Construct

from video_content_delivery.lambda_construct import LambdaConstruct
from video_content_delivery.dynamo_table import DynamoTable
from video_content_delivery.apigateway_construct import ApiGatewayConstruct

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
                           block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                           cors=[s3.CorsRule(
                               allowed_headers=["*"],
                               allowed_methods=[
                                   s3.HttpMethods.PUT,
                                   s3.HttpMethods.GET,
                                   s3.HttpMethods.POST
                               ],
                               allowed_origins=["http://localhost:3000"],
                               exposed_headers=["ETag"]
                           )]
                           )
        
        environment_l = {
            "TABLE_NAME": table_name,
            "REGION": "eu-west-1",
            "BUCKET_NAME": bucket.bucket_name,
        }
        
        # Creamos las lambdas que vamos a usar
        get_presigned_url_function = LambdaConstruct(
            self,
            "GetPresignedUrlFunction",
            handler_file="index.handler",
            path_l="video_content_delivery/src/lambda/generate_url_pre",
            function_name="GetPresignedUrlFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            table=video_table,
            environment=environment_l
        )
        print(f"Lambda GetPresignedUrlFunction ARN: {get_presigned_url_function.lambda_function.function_arn}")

        bucket.grant_read_write(get_presigned_url_function.lambda_function)

        lambda_authorizer = LambdaConstruct(
            self,
            "MyCustomAuthorizer",
            handler_file="index.handler",
            path_l="video_content_delivery/src/lambda/auth",
            function_name="apigatewayAuthorizer",
            runtime=_lambda.Runtime.PYTHON_3_12
        )
        print(f"Lambda ARN: {lambda_authorizer.lambda_function.function_arn}")

        # Create the trigger Lambda
        process_video_function = LambdaConstruct(
            self,
            "ProcessVideoFunction",
            handler_file="index.handler",
            path_l="video_content_delivery/src/lambda/process_video",
            function_name="ProcessVideoFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            table=video_table,
            environment=environment_l
        )

        # Grant S3 permissions to the Lambda
        bucket.grant_read(process_video_function.lambda_function)
        
        # Grant additional S3 permissions for playlist generation
        bucket.grant_read_write(process_video_function.lambda_function)
        
        # Add S3 PutObject notification to trigger Lambda
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED_PUT,
            s3n.LambdaDestination(process_video_function.lambda_function),
            s3.NotificationKeyFilter(suffix=".mp4")  # Optional: filter for MP4 files only
        )

        # Creamos el API Gateway
        apigateway_video = ApiGatewayConstruct(self, "MyAPIGateway")

        # Añadimos el authorizer al API Gateway
        authorizer = apigateway_video.add_authorizer_v2("AudioAuthorizer", lambda_authorizer.lambda_function)

        # Añadimos los métodos a la API Gateway
        get_url = apigateway_video.api.root.add_resource("geturl")

        get_url.add_method(
            "GET",
            apigateway.LambdaIntegration(
            get_presigned_url_function.lambda_function,
            proxy=False,
            passthrough_behavior=apigateway.PassthroughBehavior.WHEN_NO_MATCH,
            request_parameters={
                "integration.request.querystring.key": "method.request.querystring.key",
                "integration.request.querystring.action": "method.request.querystring.action"
            },
            request_templates={
                "application/json": json.dumps({
                "httpMethod": "$context.httpMethod",
                "queryStringParameters": {
                    "key": "$input.params('key')",
                    "action": "$input.params('action')"
                }
                })
            },
            integration_responses=[
                apigateway.IntegrationResponse(
                status_code="200",
                response_templates={
                    "application/json": "$input.body"
                },
                response_parameters={
                    "method.response.header.Access-Control-Allow-Origin": "'*'",
                    "method.response.header.Access-Control-Allow-Headers": "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                    "method.response.header.Access-Control-Allow-Methods": "'GET,OPTIONS'"
                }
                )
            ]
            ),
            authorization_type=apigateway.AuthorizationType.CUSTOM,
            authorizer=authorizer,
            request_parameters={
            "method.request.querystring.key": False,
            "method.request.querystring.action": True
            },
            method_responses=[
            apigateway.MethodResponse(
                status_code="200",
                response_models={
                "application/json": apigateway.Model.EMPTY_MODEL
                },
                response_parameters={
                "method.response.header.Access-Control-Allow-Origin": True,
                "method.response.header.Access-Control-Allow-Headers": True,
                "method.response.header.Access-Control-Allow-Methods": True
                }
            )
            ]
        )

        # Add OPTIONS method for CORS
        get_url.add_method(
            "OPTIONS",
            apigateway.MockIntegration(
                integration_responses=[{
                    'statusCode': '200',
                    'responseParameters': {
                        'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                        'method.response.header.Access-Control-Allow-Methods': "'GET,OPTIONS'",
                        'method.response.header.Access-Control-Allow-Origin': "'*'"
                    }
                }],
                passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                request_templates={
                    "application/json": "{\"statusCode\": 200}"
                }
            ),
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                        'method.response.header.Access-Control-Allow-Origin': True
                    }
                )
            ]
        )

        # Add API Gateway URL to CloudFormation outputs
        CfnOutput(
            self,
            "ApiGatewayUrl",
            value=f"{apigateway_video.api.url}",
            description="API Gateway endpoint URL",
            export_name=f"{construct_id}-api-url"
        )


