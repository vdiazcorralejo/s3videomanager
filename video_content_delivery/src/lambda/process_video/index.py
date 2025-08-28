import json
import os
import boto3
from datetime import datetime

s3_client = boto3.client('s3')
dynamodb = boto3.client('dynamodb')

def get_all_videos(bucket_name):
    """List all MP4 files in the bucket and format them for JSON"""
    videos = []
    print(f"Starting to list videos from bucket: {bucket_name}")
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket_name):
            contents = page.get('Contents', [])
            print(f"Found {len(contents)} objects in current page")
            
            for obj in contents:
                if obj['Key'].lower().endswith('.mp4'):
                    # Changed to simple JSON structure
                    video_info = {
                        'fileName': obj['Key'],
                        'size': obj['Size'],
                        'uploadDate': obj['LastModified'].isoformat(),
                        'contentType': 'video/mp4'
                    }
                    videos.append(video_info)
                    print(f"Added video: {obj['Key']}, Size: {obj['Size']} bytes")
                
    except Exception as e:
        print(f"Error listing objects: {str(e)}")
        raise e
    
    print(f"Total MP4 files found: {len(videos)}")
    return videos

def generate_m3u_playlist(videos, bucket_name):
    """Generate M3U playlist from video list"""
    print("\n=== Generating M3U Playlist ===")
    
    try:
        # Create M3U content
        m3u_content = "#EXTM3U\n"
        
        for video in videos:
            filename = video['fileName']
            # Generate pre-signed URL for each video with 24h expiration
            url = s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': filename
                },
                ExpiresIn=86400  # 24 hours
            )
            m3u_content += f"#EXTINF:-1,{filename}\n{url}\n"
        
        # Upload M3U file to S3
        playlist_key = 'playlist.m3u'
        s3_client.put_object(
            Bucket=bucket_name,
            Key=playlist_key,
            Body=m3u_content.encode('utf-8'),
            ContentType='application/x-mpegurl'
        )
        
        print(f"Playlist generated and uploaded as {playlist_key}")
        return playlist_key
        
    except Exception as e:
        print(f"Error generating playlist: {str(e)}")
        raise e

def handler(event, context):
    print("=== Lambda Execution Started ===")
    print(f"Event received: {json.dumps(event, indent=2)}")
    print(f"Function name: {context.function_name}")
    print(f"Memory limit: {context.memory_limit_in_mb}MB")
    
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']
    
    print(f"\n=== Processing Upload ===")
    print(f"Bucket: {bucket}")
    print(f"File: {key}")
    
    try:
        print("\n=== Getting Video List ===")
        video_list = get_all_videos(bucket)
        
        # Generate M3U playlist
        playlist_key = generate_m3u_playlist(video_list, bucket)
        
        table_name = os.environ.get('TABLE_NAME')
        if not table_name:
            print("Error: TABLE_NAME environment variable not set")
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': 'Server configuration error'
                })
            }
        print(f"\n=== Updating DynamoDB ===")
        print(f"Table: {table_name}")
        print(f"Number of videos to update: {len(video_list)}")
        
        # Convert the video list to JSON string
        video_list_json = json.dumps(video_list)
        
        response = dynamodb.put_item(
            TableName=table_name,
            Item={
                'videoList': {'S': 'all_videos'},
                'Date': {'S': 'current'},
                'videos': {'S': video_list_json},
                'lastUpdated': {'S': datetime.now().isoformat()},
                'playlistKey': {'S': playlist_key}  # Add playlist key to DynamoDB
            }
        )
        
        # Generate playlist URL
        playlist_url = s3_client.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': bucket,
                'Key': playlist_key
            },
            ExpiresIn=86400
        )
        
        print(f"\n=== DynamoDB Update Complete ===")
        print(f"Response: {json.dumps(response, indent=2)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully updated video list in DynamoDB',
                'videoCount': len(video_list),
                'lastUpdated': datetime.now().isoformat(),
                'videos': video_list,
                'playlistUrl': playlist_url
            })
        }
    except Exception as e:
        print(f"\n=== Error Occurred ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
    finally:
        print("\n=== Lambda Execution Completed ===")