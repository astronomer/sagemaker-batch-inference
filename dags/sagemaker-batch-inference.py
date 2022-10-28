"""
A batch inference pipeline using Amazon Sagemaker's Model Registry, Batch Transform, and Processing
features.
"""

from datetime import timedelta

from airflow.decorators import dag, task
from airflow.providers.amazon.aws.hooks.sagemaker import SageMakerHook

from pendulum import datetime

from airflow.providers.amazon.aws.operators.s3 import S3CopyObjectOperator
from astronomer.providers.amazon.aws.operators.sagemaker import (
    SageMakerProcessingOperatorAsync,
    SageMakerTransformOperatorAsync
)


base_folder = "astronomer-demo-dag"

output_s3_key = f"{base_folder}/predict/output/"
raw_data = f"{base_folder}/raw_data.csv"
clean_data = f"{base_folder}/predict/input/clean_data.csv"


@dag(
    start_date=datetime(2022, 8, 4),  # Best practice is to use a static start_date.
    max_active_runs=1,
    schedule_interval=None,
    # Default settings applied to all tasks within the DAG; can be overwritten at the task level.
    default_args={
        "retries": 0,
        "retry_delay": timedelta(minutes=3),
    },
    catchup=False,
    tags=["example", "aws", "sagemaker"],
    doc_md=__doc__
)
def sagemaker_batch_inference():
    copy_test = S3CopyObjectOperator(
        task_id='copy_test_data',
        source_bucket_name="sagemaker-sample-files",
        source_bucket_key="datasets/tabular/uci_abalone/preprocessed/test.csv",
        dest_bucket_name="{{ var.value.s3_bucket }}",
        dest_bucket_key=raw_data
    )

    process_data = SageMakerProcessingOperatorAsync(
        task_id='process_data',
        config={
            "ProcessingJobName": 'astronomer-prep-data-{}'.format("{{ ts_nodash }}"),
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

    @task
    def get_latest_model_version(mpg):
        """Uses the Sagemaker API to get the latest model version from a given Model Package Group
        :param mpg: Sagemaker Model Package Group name
        :return: Model name that has been created with a matching version number.
        :rtype: str
        """
        sagemaker_client = SageMakerHook().get_conn()

        registered_models = sagemaker_client.list_model_packages(
            ModelPackageGroupName=mpg
        )

        model_version = sagemaker_client.describe_model_package(
            ModelPackageName=registered_models['ModelPackageSummaryList'][0]['ModelPackageArn']
        )

        model_name = "{0}-v{1}".format(mpg, model_version['ModelPackageVersion'])

        return model_name

    model_version_name = get_latest_model_version("{{ var.value.model_package_group }}")

    predict = SageMakerTransformOperatorAsync(
        task_id='predict',
        config={
            "DataProcessing": {
                "JoinSource": "Input",
            },
            "TransformJobName": "astronomer-predict-{0}".format("{{ ts_nodash }}"),
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
            "ModelName": model_version_name
        }
    )

    copy_test >> process_data
    [process_data, model_version_name] >> predict


dag = sagemaker_batch_inference()
