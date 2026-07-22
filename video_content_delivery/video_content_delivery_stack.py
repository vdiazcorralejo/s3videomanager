import json
from aws_cdk import (
    Stack,
    Duration,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_s3_notifications as s3n,
    aws_secretsmanager as secretsmanager,
    aws_wafv2 as wafv2,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

from video_content_delivery.lambda_construct import LambdaConstruct
from video_content_delivery.dynamo_table import DynamoTable
from video_content_delivery.apigateway_construct import ApiGatewayConstruct

import aws_cdk as cdk

class VideoContentDeliveryStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create the DynamoDB table for storing video metadata
        table_name = "listOfVideoFiles"
        video_table = DynamoTable(self, table_name)
        print(f"Table ARN: {video_table.table.table_arn}")
        print(f"Table NAME: {video_table.table.table_name}")

        # Create S3 bucket for video storage with proper security and CORS configuration
        bucket = s3.Bucket(self, "VideoBucket",
                           versioned=True,
                           removal_policy=RemovalPolicy.RETAIN,
                           block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                           encryption=s3.BucketEncryption.S3_MANAGED,
                           enforce_ssl=True,
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

        # Lifecycle rules for cost optimisation (Fase 0.6)
        bucket.add_lifecycle_rule(
            id='IntelligentTiering',
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.INTELLIGENT_TIERING,
                    transition_after=Duration.days(0)
                )
            ]
        )
        bucket.add_lifecycle_rule(
            id='ArchiveOldVideos',
            transitions=[
                s3.Transition(
                    storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL,
                    transition_after=Duration.days(90)
                )
            ],
            prefix='videos/'
        )

        # Environment variables for all Lambda functions
        environment_l = {
            "TABLE_NAME": table_name,
            "REGION": "eu-west-1",
            "BUCKET_NAME": bucket.bucket_name,
        }

        jwt_secret = secretsmanager.Secret(
            self,
            "JwtSecret",
            secret_name="video-content-delivery-jwt-secret",
            removal_policy=RemovalPolicy.RETAIN,
        )
        jwt_environment = {
            **environment_l,
            "JWT_SECRET_NAME": jwt_secret.secret_name,
        }

        # Create Lambda function for generating presigned URLs
        get_presigned_url_function = LambdaConstruct(
            self,
            "GetPresignedUrlFunction",
            handler_file="index.handler",
            path_l="video_content_delivery/src/lambda/generate_url_pre",
            function_name="GetPresignedUrlFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            memory_size=256,
            table=video_table,
            environment=environment_l
        )
        print(f"Lambda GetPresignedUrlFunction ARN: {get_presigned_url_function.lambda_function.function_arn}")

        # Grant S3 permissions to the presigned URL function
        bucket.grant_read_write(get_presigned_url_function.lambda_function)

        # Create Lambda authorizer for API Gateway authentication
        lambda_authorizer = LambdaConstruct(
            self,
            "MyCustomAuthorizer",
            handler_file="index.handler",
            path_l="video_content_delivery/src/lambda/auth",
            function_name="apigatewayAuthorizer",
            runtime=_lambda.Runtime.PYTHON_3_12,
            environment=jwt_environment,
        )
        print(f"Lambda ARN: {lambda_authorizer.lambda_function.function_arn}")
        jwt_secret.grant_read(lambda_authorizer.lambda_function)

        # Create Lambda function for processing uploaded videos
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

        # Create Lambda function for token generation
        token_generator_function = LambdaConstruct(
            self,
            "TokenGeneratorFunction",
            handler_file="index.handler",
            path_l="video_content_delivery/src/lambda/token_generator",
            function_name="TokenGeneratorFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            environment=jwt_environment,
        )
        jwt_secret.grant_read(token_generator_function.lambda_function)

        # Create Lambda function for catalog retrieval
        catalog_function = LambdaConstruct(
            self,
            "CatalogFunction",
            handler_file="index.handler",
            path_l="video_content_delivery/src/lambda/catalog",
            function_name="CatalogFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            table=video_table,
            environment=environment_l
        )

        # Grant S3 permissions to the video processing Lambda
        bucket.grant_read(process_video_function.lambda_function)

        # Grant additional S3 permissions for playlist generation
        bucket.grant_read_write(process_video_function.lambda_function)

        # Configure S3 to trigger Lambda when MP4 files are uploaded
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED_PUT,
            s3n.LambdaDestination(process_video_function.lambda_function),  # type: ignore[arg-type]
            s3.NotificationKeyFilter(suffix=".mp4")  # Only trigger for MP4 files
        )

        # Create API Gateway for REST endpoints
        apigateway_video = ApiGatewayConstruct(self, "MyAPIGateway")

        # Add a regional WAF WebACL with basic managed protections
        waf_web_acl = wafv2.CfnWebACL(
            self,
            "VideoApiWafWebAcl",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name="VideoApiWaf",
                sampled_requests_enabled=True,
            ),
            rules=[
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=1,
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            name="AWSManagedRulesCommonRuleSet",
                            vendor_name="AWS",
                        )
                    ),
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="CommonRuleSet",
                        sampled_requests_enabled=True,
                    ),
                )
            ],
        )

        # Attach the WAF ACL to API Gateway stage via association resource
        wafv2.CfnWebACLAssociation(
            self,
            "VideoApiWafAssociation",
            resource_arn=f"arn:aws:apigateway:{cdk.Aws.REGION}::/restapis/{apigateway_video.api.rest_api_id}/stages/prod",
            web_acl_arn=waf_web_acl.attr_arn,
        )

        # Add error responses for better error handling
        apigateway_video.add_error_responses()

        # Add custom authorizer to API Gateway
        authorizer = apigateway_video.add_authorizer_v2("AudioAuthorizer", lambda_authorizer.lambda_function)

        # Create the /geturl resource and methods
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

        # Create the /catalog resource and method (protected by JWT authorizer)
        catalog = apigateway_video.api.root.add_resource("catalog")
        catalog.add_method(
            "GET",
            apigateway.LambdaIntegration(catalog_function.lambda_function),
            authorization_type=apigateway.AuthorizationType.CUSTOM,
            authorizer=authorizer,
            request_parameters={
                "method.request.querystring.pageSize": False,
                "method.request.querystring.lastEvaluatedKey": False,
                "method.request.querystring.status": False,
            }
        )

        # Note: OPTIONS method is automatically added by default_cors_preflight_options in ApiGatewayConstruct

        # Add CloudFormation outputs for easy access
        CfnOutput(
            self,
            "ApiGatewayUrl",
            value=f"{apigateway_video.api.url}",
            description="API Gateway endpoint URL",
            export_name=f"{construct_id}-api-url"
        )

        CfnOutput(
            self,
            "GetUrlEndpoint",
            value=f"{apigateway_video.api.url}geturl",
            description="GetURL endpoint for video operations"
        )

        CfnOutput(
            self,
            "CatalogEndpoint",
            value=f"{apigateway_video.api.url}catalog",
            description="Catalog endpoint for video listings"
        )

        CfnOutput(
            self,
            "BucketName",
            value=bucket.bucket_name,
            description="S3 bucket name for video storage",
            export_name=f"{construct_id}-bucket-name"
        )

        CfnOutput(
            self,
            "DynamoDBTableName",
            value=video_table.table.table_name,
            description="DynamoDB table name for video metadata",
            export_name=f"{construct_id}-table-name"
        )

