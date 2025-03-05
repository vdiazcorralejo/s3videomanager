from aws_cdk import RemovalPolicy
from aws_cdk import aws_dynamodb as dynamodb
from constructs import Construct

class DynamoTable:
    def __init__(self, scope: Construct, id: str) -> None:
        # Crear la tabla DynamoDB
        self.table = dynamodb.Table(
            scope,
            id,
            table_name=id,
            sort_key=dynamodb.Attribute(
                name="creationDate",
                type=dynamodb.AttributeType.STRING
            ),
            partition_key=dynamodb.Attribute(
                name="videoId",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,  # Cambiar a PROVISIONED si es necesario
            removal_policy=RemovalPolicy.DESTROY,  # Cambiar a RETAIN en producción
        )

        # Añadir un índice global secundario (GSI) para 'status' y 'creationDate'
        self.table.add_global_secondary_index(
            index_name="StatusIndex",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="creationDate",
                type=dynamodb.AttributeType.STRING
            ),
            projection_type=dynamodb.ProjectionType.ALL
        )
        