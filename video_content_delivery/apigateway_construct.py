from aws_cdk import (
    RemovalPolicy,
    aws_apigateway as apigateway,
    aws_lambda as _lambda,
    Stack,
    RemovalPolicy,
    Duration,
    aws_iam as iam,
    aws_logs as logs
)
import logging
from constructs import Construct

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
                data_trace_enabled=True 
            ),
            description='API Gateway to manage video content'
        )

    def add_authorizer(self, authorizer_name: str, authorizer_function: _lambda.Function) -> apigateway.CfnAuthorizer:
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
    
    def add_authorizer_v2(self, authorizer_name: str, authorizer_function: _lambda.Function) -> apigateway.RequestAuthorizer:
        """Método para añadir un authorizer a alto nivel"""
        # Create Lambda Authorizer Token Type
        authorizer = apigateway.TokenAuthorizer(
            self, authorizer_name,
            handler=authorizer_function,
            identity_source="method.request.header.Authorization",
            results_cache_ttl=Duration.seconds(0)
        )
        return authorizer

    def add_resource_with_method(self, path: str, method: str, integration: apigateway.Integration, authorizer: apigateway.RequestAuthorizer) -> None:
        """Método para añadir recursos y métodos al API Gateway"""
        new_resource = self.api.root.add_resource(path)
        new_resource.add_method(
            method,
            integration,
            authorization_type=apigateway.AuthorizationType.CUSTOM if authorizer else apigateway.AuthorizationType.NONE,
            authorizer=authorizer
        )       
