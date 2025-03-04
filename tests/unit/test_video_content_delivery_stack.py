import aws_cdk as core
import aws_cdk.assertions as assertions

from video_content_delivery.video_content_delivery_stack import VideoContentDeliveryStack

# example tests. To run these tests, uncomment this file along with the example
# resource in video_content_delivery/video_content_delivery_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = VideoContentDeliveryStack(app, "video-content-delivery")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
