from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

class DynamoTable:
    def __init__(self, scope: Construct, id: str) -> None:
        # Create DynamoDB table
        self.table = dynamodb.Table(
            scope,
            id,
            table_name=id,
            partition_key=dynamodb.Attribute(
                name="videoList",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="Date",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Keep the existing PK/SK to avoid replacing the table in this phase.
        # The catalog flow will use videoList='catalog' and Date as the item identifier.
        self.table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(
                name="videoList",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )

        self.table.add_global_secondary_index(
            index_name="UploadDateIndex",
            partition_key=dynamodb.Attribute(
                name="videoList",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="uploadDate",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
