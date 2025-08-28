import aws_cdk as core
import aws_cdk.assertions as assertions
from video_content_delivery.video_content_delivery_stack import VideoContentDeliveryStack

def test_s3_bucket_created():
    # ARRANGE
    app = core.App()
    stack = VideoContentDeliveryStack(app, "video-content-delivery")
    
    # ACT
    template = assertions.Template.from_stack(stack)

    # ASSERT
    template.has_resource_properties("AWS::S3::Bucket", {
        "BucketName": "video-content-delivery-bucket",
        "VersioningConfiguration": {
            "Status": "Enabled"
        },
        "CorsConfiguration": {
            "CorsRules": [{
                "AllowedHeaders": ["*"],
                "AllowedMethods": ["PUT", "GET", "POST"],
                "AllowedOrigins": ["http://localhost:3000"],
                "ExposedHeaders": ["ETag"]
            }]
        }
    })

def test_dynamodb_table_created():
    # ARRANGE
    app = core.App()
    stack = VideoContentDeliveryStack(app, "video-content-delivery")
    
    # ACT
    template = assertions.Template.from_stack(stack)

    # ASSERT
    template.has_resource_properties("AWS::DynamoDB::Table", {
        "TableName": "listOfVideoFiles",
        "BillingMode": "PAY_PER_REQUEST"
    })

def test_lambda_functions_created():
    # ARRANGE
    app = core.App()
    stack = VideoContentDeliveryStack(app, "video-content-delivery")
    
    # ACT
    template = assertions.Template.from_stack(stack)

    # ASSERT
    # Verificar que se crean las funciones Lambda (includes CloudWatch log group functions)
    template.resource_count_is("AWS::Lambda::Function", 5)  # Verifica que hay 5 funciones Lambda
    
    # Verificar la función GetPresignedUrl
    template.has_resource_properties("AWS::Lambda::Function", {
        "Handler": "index.handler",
        "Runtime": "python3.12",
        "FunctionName": "GetPresignedUrlFunction",
        "Environment": {
            "Variables": {
                "TABLE_NAME": "listOfVideoFiles",
                "REGION": "eu-west-1"
            }
        }
    })

def test_api_gateway_created():
    # ARRANGE
    app = core.App()
    stack = VideoContentDeliveryStack(app, "video-content-delivery")
    
    # ACT
    template = assertions.Template.from_stack(stack)

    # ASSERT
    # Verificar API Gateway
    template.has_resource_properties("AWS::ApiGateway::RestApi", {
        "Name": "MyVideoFilesAPI",
        "EndpointConfiguration": {
            "Types": ["REGIONAL"]
        }
    })
    
    # Verificar método GET
    template.has_resource_properties("AWS::ApiGateway::Method", {
        "HttpMethod": "GET",
        "AuthorizationType": "CUSTOM"
    })

def test_authorizer_created():
    # ARRANGE
    app = core.App()
    stack = VideoContentDeliveryStack(app, "video-content-delivery")
    
    # ACT
    template = assertions.Template.from_stack(stack)

    # ASSERT
    template.has_resource_properties("AWS::ApiGateway::Authorizer", {
        "Type": "TOKEN",
        "IdentitySource": "method.request.header.Authorization"
    })
