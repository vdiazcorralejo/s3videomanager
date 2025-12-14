from aws_cdk import (
    RemovalPolicy,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    Stack,
    Duration,
    aws_iam as iam,
    aws_logs as logs
)
import logging
from constructs import Construct
from typing import Optional

class ApiGatewayConstruct(Construct):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #Creamos el loggroup
        log_group = logs.LogGroup(
            self,
            "ApiGatewayLogGroup",
            log_group_name="MyVideoFilesAPILogGroup",
            retention=logs.RetentionDays.ONE_WEEK,
            removal_policy=RemovalPolicy.DESTROY
        ) 

        # Crear el API Gateway REST API
        self.api = apigateway.RestApi(
            self, 'MyApiGateway',
            rest_api_name='MyVideoFilesAPI',
            endpoint_configuration=apigateway.EndpointConfiguration(
                types=[apigateway.EndpointType.REGIONAL]
            ),
            deploy_options=apigateway.StageOptions(
                access_log_destination=apigateway.LogGroupLogDestination(log_group),
                access_log_format=apigateway.AccessLogFormat.json_with_standard_fields(
                        caller=True,
                        http_method=True,
                        ip=True,
                        protocol=True,
                        request_time=True,
                        resource_path=True,
                        response_length=True,
                        status=True,
                        user=True,
                ),
                logging_level=apigateway.MethodLoggingLevel.INFO, 
                data_trace_enabled=True,
                # Add throttling to prevent abuse
                throttling_rate_limit=100,  # Requests per second
                throttling_burst_limit=200,  # Burst capacity
                # Add metrics to monitor API usage
                metrics_enabled=True
            ),
            description='API Gateway to manage video content',
            # Add default CORS configuration
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["http://localhost:3000"],
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token"
                ],
                allow_credentials=True,
                max_age=Duration.minutes(5)
            ),
            # Enable CloudWatch role for API Gateway to push logs
            cloud_watch_role=True
        )

    def add_authorizer(self, authorizer_name: str, authorizer_function: _lambda.IFunction) -> apigateway.CfnAuthorizer:
        """Método para añadir un authorizer a bajo nivel"""
        # Obtener la región del stack
        region = Stack.of(self).region
        authorizer = apigateway.CfnAuthorizer(
            self, authorizer_name,
            rest_api_id=self.api.rest_api_id,
            name=authorizer_name,
            type="TOKEN",
            authorizer_uri=f"arn:aws:apigateway:{region}:lambda:path/2015-03-31/functions/{authorizer_function.function_arn}/invocations",
            auth_type="CUSTOM",
            identity_source="method.request.header.Authorization"
        )
        # Agregar un mensaje de registro para depurar el ID del autorizer
        logging.info(f"Authorizer created with ID: {authorizer.ref}")
        print(f"Authorizer created with ID: {authorizer.ref}")
        return authorizer
    
    def add_authorizer_v2(self, authorizer_name: str, authorizer_function: _lambda.IFunction) -> apigateway.IAuthorizer:
        """Método para añadir un authorizer a alto nivel"""
        # Create Lambda Authorizer Token Type
        authorizer = apigateway.TokenAuthorizer(
            self, authorizer_name,
            handler=authorizer_function,
            identity_source="method.request.header.Authorization",
            results_cache_ttl=Duration.seconds(0)
        )
        return authorizer

    def add_resource_with_method(self, path: str, method: str, integration: apigateway.Integration, authorizer: Optional[apigateway.IAuthorizer] = None) -> apigateway.Resource:
        """Método para añadir recursos y métodos al API Gateway"""
        new_resource = self.api.root.add_resource(path)
        new_resource.add_method(
            method,
            integration,
            authorization_type=apigateway.AuthorizationType.CUSTOM if authorizer else apigateway.AuthorizationType.NONE,
            authorizer=authorizer
        )
        return new_resource
    
    def add_cors_options(self, resource: apigateway.Resource, allowed_methods: Optional[list[str]] = None) -> None:
        """Add CORS OPTIONS method to a resource"""
        if allowed_methods is None:
            allowed_methods = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
        
        resource.add_method(
            "OPTIONS",
            apigateway.MockIntegration(
                integration_responses=[{
                    'statusCode': '200',
                    'responseParameters': {
                        'method.response.header.Access-Control-Allow-Headers': "'Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token'",
                        'method.response.header.Access-Control-Allow-Methods': f"'{','.join(allowed_methods)}'",
                        'method.response.header.Access-Control-Allow-Origin': "'http://localhost:3000'",
                        'method.response.header.Access-Control-Allow-Credentials': "'true'"
                    }
                }],
                passthrough_behavior=apigateway.PassthroughBehavior.NEVER,
                request_templates={
                    "application/json": '{"statusCode": 200}'
                }
            ),
            method_responses=[
                apigateway.MethodResponse(
                    status_code="200",
                    response_parameters={
                        'method.response.header.Access-Control-Allow-Headers': True,
                        'method.response.header.Access-Control-Allow-Methods': True,
                        'method.response.header.Access-Control-Allow-Origin': True,
                        'method.response.header.Access-Control-Allow-Credentials': True
                    }
                )
            ]
        )
    
    def add_error_responses(self) -> None:
        """Add standard error response models to API Gateway"""
        # Add Gateway Response for unauthorized access
        self.api.add_gateway_response(
            "UnauthorizedResponse",
            type=apigateway.ResponseType.UNAUTHORIZED,
            status_code="401",
            response_headers={
                "Access-Control-Allow-Origin": "'http://localhost:3000'",
                "Access-Control-Allow-Credentials": "'true'"
            },
            templates={
                "application/json": '{"message": "Unauthorized", "error": "$context.error.messageString"}'
            }
        )
        
        # Add Gateway Response for access denied
        self.api.add_gateway_response(
            "AccessDeniedResponse",
            type=apigateway.ResponseType.ACCESS_DENIED,
            status_code="403",
            response_headers={
                "Access-Control-Allow-Origin": "'http://localhost:3000'",
                "Access-Control-Allow-Credentials": "'true'"
            },
            templates={
                "application/json": '{"message": "Access Denied", "error": "$context.error.messageString"}'
            }
        )
        
        # Add Gateway Response for invalid API key
        self.api.add_gateway_response(
            "InvalidApiKeyResponse",
            type=apigateway.ResponseType.INVALID_API_KEY,
            status_code="403",
            response_headers={
                "Access-Control-Allow-Origin": "'http://localhost:3000'",
                "Access-Control-Allow-Credentials": "'true'"
            },
            templates={
                "application/json": '{"message": "Invalid API Key", "error": "$context.error.messageString"}'
            }
        )
        
        # Add Gateway Response for throttled requests
        self.api.add_gateway_response(
            "ThrottledResponse",
            type=apigateway.ResponseType.THROTTLED,
            status_code="429",
            response_headers={
                "Access-Control-Allow-Origin": "'http://localhost:3000'",
                "Access-Control-Allow-Credentials": "'true'"
            },
            templates={
                "application/json": '{"message": "Too Many Requests", "error": "Rate limit exceeded"}'
            }
        )
        
        # Add Gateway Response for default 4xx errors
        self.api.add_gateway_response(
            "Default4xxResponse",
            type=apigateway.ResponseType.DEFAULT_4_XX,
            response_headers={
                "Access-Control-Allow-Origin": "'http://localhost:3000'",
                "Access-Control-Allow-Credentials": "'true'"
            }
        )
        
        # Add Gateway Response for default 5xx errors
        self.api.add_gateway_response(
            "Default5xxResponse",
            type=apigateway.ResponseType.DEFAULT_5_XX,
            response_headers={
                "Access-Control-Allow-Origin": "'http://localhost:3000'",
                "Access-Control-Allow-Credentials": "'true'"
            }
        )       
