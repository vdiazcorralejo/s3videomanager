import json
import os
from aws_cdk import (
    Stack,
    Duration,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_s3_notifications as s3n,
    aws_secretsmanager as secretsmanager,
    aws_sqs as sqs,
    aws_sns as sns,
    aws_cloudwatch as cloudwatch,
    aws_cloudwatch_actions as cloudwatch_actions,
    aws_wafv2 as wafv2,
    aws_iam as iam,
    aws_logs as logs,
    RemovalPolicy,
    CfnOutput,
)
from constructs import Construct

from video_content_delivery.lambda_construct import LambdaConstruct
from video_content_delivery.dynamo_table import DynamoTable
from video_content_delivery.apigateway_construct import ApiGatewayConstruct

import aws_cdk as cdk

class VideoContentDeliveryStack(Stack):

    def _resolve_environment_name(self) -> str:
        raw_value = (
            self.node.try_get_context("environment")
            or self.node.try_get_context("env")
            or os.getenv("CDK_ENVIRONMENT")
            or os.getenv("ENVIRONMENT")
            or "dev"
        )
        env_name = str(raw_value).strip().lower()
        if env_name in {"prod", "production", "prd"}:
            return "prod"
        if env_name in {"staging", "stage", "stg", "preprod", "pre-production"}:
            return "staging"
        return "dev"

    def _get_removal_policy(self) -> RemovalPolicy:
        return RemovalPolicy.RETAIN if self.environment_name == "prod" else RemovalPolicy.DESTROY

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.environment_name = self._resolve_environment_name()
        self.is_production = self.environment_name == "prod"
        self.is_non_production = not self.is_production

        lambda_memory_size = 512 if self.is_production else 128
        lambda_timeout = Duration.seconds(30 if self.is_production else 15)
        log_retention = logs.RetentionDays.ONE_MONTH if self.is_production else logs.RetentionDays.ONE_WEEK
        log_removal_policy = RemovalPolicy.RETAIN if self.is_production else RemovalPolicy.DESTROY

        # Create the DynamoDB table for storing video metadata
        table_name = "listOfVideoFiles"
        video_table = DynamoTable(self, table_name, environment_name=self.environment_name, is_production=self.is_production)
        print(f"Table ARN: {video_table.table.table_arn}")
        print(f"Table NAME: {video_table.table.table_name}")

        # Create S3 bucket for video storage with proper security and CORS configuration
        bucket = s3.Bucket(self, "VideoBucket",
                           versioned=self.is_production,
                           removal_policy=self._get_removal_policy(),
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

        # Lifecycle rules for cost optimisation and production safety
        if self.is_production:
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
        else:
            bucket.add_lifecycle_rule(
                id='ArchiveOldVideos',
                transitions=[
                    s3.Transition(
                        storage_class=s3.StorageClass.GLACIER_INSTANT_RETRIEVAL,
                        transition_after=Duration.days(30)
                    )
                ],
                prefix='videos/'
            )
            bucket.add_lifecycle_rule(
                id='DeleteIncompleteUploads',
                expiration=Duration.days(1)
            )

        # Environment variables for all Lambda functions
        environment_l = {
            "TABLE_NAME": table_name,
            "REGION": self.region or "eu-west-1",
            "BUCKET_NAME": bucket.bucket_name,
        }

        jwt_secret = secretsmanager.Secret(
            self,
            "JwtSecret",
            secret_name=f"video-content-delivery-jwt-secret-{self.environment_name}",
            removal_policy=self._get_removal_policy(),
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
            memory_size=lambda_memory_size,
            timeout=lambda_timeout,
            log_retention=log_retention,
            log_removal_policy=log_removal_policy,
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
            memory_size=lambda_memory_size,
            timeout=lambda_timeout,
            log_retention=log_retention,
            log_removal_policy=log_removal_policy,
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
            memory_size=lambda_memory_size,
            timeout=lambda_timeout,
            log_retention=log_retention,
            log_removal_policy=log_removal_policy,
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
            memory_size=lambda_memory_size,
            timeout=lambda_timeout,
            log_retention=log_retention,
            log_removal_policy=log_removal_policy,
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
            memory_size=lambda_memory_size,
            timeout=lambda_timeout,
            log_retention=log_retention,
            log_removal_policy=log_removal_policy,
            environment=environment_l
        )

        # Create SQS queue for resilient video processing with DLQ
        process_video_dlq = sqs.Queue(
            self,
            "ProcessVideoDLQ",
            retention_period=Duration.days(14),
            removal_policy=self._get_removal_policy(),
        )
        process_video_queue = sqs.Queue(
            self,
            "ProcessVideoQueue",
            visibility_timeout=Duration.seconds(60),
            dead_letter_queue=sqs.DeadLetterQueue(
                queue=process_video_dlq,
                max_receive_count=3,
            ),
            removal_policy=self._get_removal_policy(),
        )

        # Grant S3 permissions to the video processing Lambda
        bucket.grant_read(process_video_function.lambda_function)

        # Grant additional S3 permissions for playlist generation
        bucket.grant_read_write(process_video_function.lambda_function)

        # Configure S3 to enqueue processing events for uploaded MP4 files
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED_PUT,
            s3n.SqsDestination(process_video_queue),
            s3.NotificationKeyFilter(suffix=".mp4")
        )

        process_video_queue.grant_consume_messages(process_video_function.lambda_function)
        _lambda.EventSourceMapping(
            self,
            "ProcessVideoQueueEventSource",
            target=process_video_function.lambda_function,
            event_source_arn=process_video_queue.queue_arn,
            batch_size=1,
            starting_position=_lambda.StartingPosition.TRIM_HORIZON,
        )

        # Create API Gateway for REST endpoints
        apigateway_video = ApiGatewayConstruct(
            self,
            "MyAPIGateway",
            environment_name=self.environment_name,
        )

        monitoring_topic = sns.Topic(
            self,
            "VideoDeliveryMonitoringTopic",
            display_name="Video Delivery Monitoring",
            topic_name=f"video-delivery-monitoring-{self.environment_name}",
        )
        monitoring_subscription = sns.Subscription(
            self,
            "VideoDeliveryMonitoringSubscription",
            topic=monitoring_topic,
            protocol=sns.SubscriptionProtocol.EMAIL,
            endpoint="ops@example.com",
        )

        api_5xx_alarm = cloudwatch.Alarm(
            self,
            "ApiGateway5xxAlarm",
            metric=apigateway_video.api.metric_server_error(),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_name=f"{construct_id}-api-5xx",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
            actions_enabled=True,
        )
        api_5xx_alarm.add_alarm_action(cloudwatch_actions.SnsAction(monitoring_topic))

        lambda_errors_alarm = cloudwatch.Alarm(
            self,
            "ProcessVideoLambdaErrorsAlarm",
            metric=process_video_function.lambda_function.metric_errors(),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_name=f"{construct_id}-process-video-errors",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        lambda_errors_alarm.add_alarm_action(cloudwatch_actions.SnsAction(monitoring_topic))

        lambda_duration_alarm = cloudwatch.Alarm(
            self,
            "ProcessVideoLambdaDurationAlarm",
            metric=process_video_function.lambda_function.metric_duration(statistic="p99"),
            threshold=max(1, int(lambda_timeout.to_seconds() * 0.8)),
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_name=f"{construct_id}-process-video-duration",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        lambda_duration_alarm.add_alarm_action(cloudwatch_actions.SnsAction(monitoring_topic))

        lambda_throttles_alarm = cloudwatch.Alarm(
            self,
            "ProcessVideoLambdaThrottlesAlarm",
            metric=process_video_function.lambda_function.metric_throttles(),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_name=f"{construct_id}-process-video-throttles",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        lambda_throttles_alarm.add_alarm_action(cloudwatch_actions.SnsAction(monitoring_topic))

        dlq_alarm = cloudwatch.Alarm(
            self,
            "ProcessVideoDlqAlarm",
            metric=process_video_dlq.metric_approximate_number_of_messages_visible(),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_name=f"{construct_id}-process-video-dlq",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        dlq_alarm.add_alarm_action(cloudwatch_actions.SnsAction(monitoring_topic))

        dynamodb_throttles_alarm = cloudwatch.Alarm(
            self,
            "DynamoDbThrottlesAlarm",
            metric=video_table.table.metric_throttled_requests_for_operation(
                "PutItem",
                statistic="Sum",
            ),
            threshold=1,
            evaluation_periods=1,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_OR_EQUAL_TO_THRESHOLD,
            alarm_name=f"{construct_id}-dynamodb-throttles",
            treat_missing_data=cloudwatch.TreatMissingData.NOT_BREACHING,
        )
        dynamodb_throttles_alarm.add_alarm_action(cloudwatch_actions.SnsAction(monitoring_topic))

        cloudwatch.Dashboard(
            self,
            "VideoDeliveryDashboard",
            dashboard_name=f"{construct_id}-operations",
            widgets=[
                [
                    cloudwatch.GraphWidget(
                        title="API Gateway 5XX",
                        left=[apigateway_video.api.metric_server_error()],
                    )
                ],
                [
                    cloudwatch.GraphWidget(
                        title="Process Video Lambda Errors",
                        left=[process_video_function.lambda_function.metric_errors()],
                    )
                ],
                [
                    cloudwatch.GraphWidget(
                        title="DLQ Approximate Messages",
                        left=[process_video_dlq.metric_approximate_number_of_messages_visible()],
                    )
                ],
            ],
        )

        # Add a regional WAF WebACL with basic managed protections in production only
        if self.is_production:
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

