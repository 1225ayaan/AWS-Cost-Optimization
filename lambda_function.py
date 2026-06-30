import boto3
import os
import logging
from datetime import datetime, timezone, timedelta

# Logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS Clients
ec2 = boto3.client('ec2')
sns = boto3.client('sns')

# Environment Variable
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']


def lambda_handler(event, context):

    deleted_volumes = []
    stopped_instances = []
    deleted_snapshots = []

    # -----------------------------
    # Delete Unattached EBS Volumes
    # -----------------------------
    volumes = ec2.describe_volumes(
        Filters=[
            {
                'Name': 'status',
                'Values': ['available']
            }
        ]
    )

    for volume in volumes['Volumes']:
        volume_id = volume['VolumeId']

        try:
            ec2.delete_volume(VolumeId=volume_id)
            deleted_volumes.append(volume_id)
        except Exception as e:
            logger.error(f"Unable to delete volume {volume_id}: {e}")

    # -----------------------------
    # Find Stopped EC2 Instances
    # -----------------------------
    reservations = ec2.describe_instances(
        Filters=[
            {
                'Name': 'instance-state-name',
                'Values': ['stopped']
            }
        ]
    )

    for reservation in reservations['Reservations']:
        for instance in reservation['Instances']:
            stopped_instances.append(instance['InstanceId'])

    # -----------------------------
    # Delete Snapshots Older Than 30 Days
    # -----------------------------
    snapshots = ec2.describe_snapshots(
        OwnerIds=['self']
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    for snapshot in snapshots['Snapshots']:

        if snapshot['StartTime'] < cutoff:

            snapshot_id = snapshot['SnapshotId']

            try:
                ec2.delete_snapshot(
                    SnapshotId=snapshot_id
                )

                deleted_snapshots.append(snapshot_id)

            except Exception as e:
                logger.error(f"Unable to delete snapshot {snapshot_id}: {e}")

    # -----------------------------
    # CloudWatch Logs
    # -----------------------------
    logger.info(f"Deleted Volumes: {deleted_volumes}")
    logger.info(f"Stopped Instances: {stopped_instances}")
    logger.info(f"Deleted Snapshots: {deleted_snapshots}")

    # -----------------------------
    # SNS Email
    # -----------------------------
    message = f"""
AWS Cost Optimization Report

Deleted Volumes:
{deleted_volumes}

Stopped EC2 Instances:
{stopped_instances}

Deleted Snapshots:
{deleted_snapshots}
"""

    sns.publish(
        TopicArn=SNS_TOPIC_ARN,
        Subject="AWS Cost Optimization Report",
        Message=message
    )

    return {
        "statusCode": 200,
        "Deleted Volumes": deleted_volumes,
        "Stopped Instances": stopped_instances,
        "Deleted Snapshots": deleted_snapshots
    }