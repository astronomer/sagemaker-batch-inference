from datetime import timedelta
from pendulum import datetime

import boto3
from airflow.decorators import dag, task, task_group
from airflow.providers.amazon.aws.operators.sagemaker import (
    SageMakerProcessingOperator,
    SageMakerTransformOperator,
)
from airflow.providers.amazon.aws.hooks.sagemaker import SageMakerHook

output_s3_key = "experiments-demo/predict/output/"
raw_data = "experiments-demo/validation.csv"
clean_data = "experiments-demo/predict/input/clean_data.csv"


@dag(
    start_date=datetime(2022, 8, 4),  # Best practice is to use a static start_date.
    max_active_runs=1,
    schedule_interval=None,
    # Default settings applied to all tasks within the DAG; can be overwritten at the task level.
    default_args={
        "retries": 0,
        "retry_delay": timedelta(minutes=3),
        'aws_conn_id': 'aws_default'
    },
    # default_view="grid",
    catchup=False,
    tags=["example", "aws", "sagemaker"],
)
def sagemaker_batch_inference_processing():
    """
    This demonstrates a batch inference pipeline using Amazon Sagemaker's Model Registry, Batch Transform, and Processing
    features.
    """

    process_data = SageMakerProcessingOperator(
        task_id='process_data',
        config={
            "ProcessingJobName": 'astronomer-blogpost-batch-infer-{}'.format("{{ ts_nodash }}"),
            "ProcessingInputs": [
                {
                    "InputName": "input",
                    "AppManaged": False,
                    "S3Input": {
                        "S3Uri": 's3://{0}/{1}'.format("{{ var.value.s3_bucket }}", raw_data),
                        "LocalPath": "/opt/ml/processing/input",
                        "S3DataType": "S3Prefix",
                        "S3InputMode": "File",
                        "S3DataDistributionType": "FullyReplicated",
                        "S3CompressionType": "None",
                    },
                },
            ],
            "ProcessingOutputConfig": {
                "Outputs": [
                    {
                        "OutputName": "output",
                        "S3Output": {
                            "S3Uri": 's3://{0}/{1}'.format("{{ var.value.s3_bucket }}", clean_data),
                            "LocalPath": "/opt/ml/processing/output",
                            "S3UploadMode": "EndOfJob",
                        },
                        "AppManaged": False,
                    }
                ]
            },
            "ProcessingResources": {
                "ClusterConfig": {
                    'InstanceCount': 1,
                    'InstanceType': 'ml.t3.medium',
                    'VolumeSizeInGB': 1,
                }
            },
            "StoppingCondition": {"MaxRuntimeInSeconds": 300},
            "AppSpecification": {
                "ImageUri": "{{ var.value.ecr_repository_uri }}",
            },
            "RoleArn": "{{ var.value.role_arn }}",
        }
    )

    @task(task_id='get_latest_model_version')
    def get_latest_model_version(mpg):
        sagemaker_hook = SageMakerHook()

        sagemaker_client = sagemaker_hook.get_conn()

        # sagemaker_client = boto3.client('sagemaker')
        registered_models = sagemaker_client.list_model_packages(
            ModelPackageGroupName=mpg
        )

        model_version = sagemaker_client.describe_model_package(
            ModelPackageName=registered_models['ModelPackageSummaryList'][0]['ModelPackageArn']
        )

        model_name = "astronomer-blogpost-v{}".format(model_version['ModelPackageVersion'])

        return model_name

    predict = SageMakerTransformOperator(
        task_id='predict',
        config={
            "DataProcessing": {
                "JoinSource": "Input",
            },
            "TransformJobName": "astronomer-blogpost-job-{0}".format("{{ ts_nodash }}"),
            "TransformInput": {
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": "s3://{0}/{1}".format("{{ var.value.s3_bucket }}", clean_data)
                    }
                },
                "ContentType": "text/csv",
                "SplitType": "Line"
            },
            "TransformOutput": {
                "S3OutputPath": "s3://{0}/{1}".format("{{ var.value.s3_bucket }}", output_s3_key),
                "Accept": "text/csv",
                "AssembleWith": "Line",
            },
            "TransformResources": {
                "InstanceCount": 1,
                "InstanceType": "ml.m5.xlarge"
            },
            "ModelName": "{{ ti.xcom_pull(task_ids='get_latest_model_version') }}"
        }
    )

    [process_data, get_latest_model_version("{{ var.value.model_package_group }}")] >> predict


dag = sagemaker_batch_inference_processing()
