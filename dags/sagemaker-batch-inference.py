import json
from datetime import datetime, timedelta
from airflow.decorators import dag, task
import boto3

from airflow.providers.amazon.aws.operators.sagemaker import SageMakerTransformOperator, SageMakerModelOperator

s3_bucket = 'sagemaker-studio-936535839574-hbsr94yskx5'
input_s3_key = 'blogpost/input'
output_s3_key = 'blogpost/output/'

@dag(
    start_date=datetime(2022, 8, 4),  # Best practice is to use a static start_date.
    max_active_runs=1,
    schedule_interval=None,
    # Default settings applied to all tasks within the DAG; can be overwritten at the task level.
    default_args={
        "retries": 0,
        "retry_delay": timedelta(minutes=3),
        'aws_conn_id': 'aws-sagemaker'
    },
    # default_view="grid",
    catchup=False,
    tags=["example", "aws", "sagemaker"],
)
def sagemaker_batch_inference():
    """
    This demonstrates a batch inference pipeline using Amazon Sagemaker's Batch Transform.
    """

    # @task(task_id='get_transform_model_version')
    # def get_transform_model_version():
    #
    #     sagemaker_client = boto3.client('sagemaker')
    #     registered_models = sagemaker_client.list_model_packages(ModelPackageGroupName="sagemaker-blogpost")
    #
    #     model_version = sagemaker_client.describe_model_package(
    #         ModelPackageName=registered_models['ModelPackageSummaryList'][0]['ModelPackageArn']
    #     )
    #
    #     model_name = "{0}-v{1}".format(model_version['ModelPackageGroupName'], model_version['ModelPackageVersion'])
    #
    #     return model_name
    #
    #     # transform_config = {
    #     #     "BatchStrategy": "SingleRecord",
    #     #     "TransformJobName": "astro-churn-{0}".format(kwargs['ts_nodash']),
    #     #     "TransformInput": {
    #     #         "DataSource": {
    #     #             "S3DataSource": {
    #     #                 "S3DataType": "S3Prefix",
    #     #                 "S3Uri": "s3://{0}/{1}/input.jsonl".format(s3_bucket, input_s3_key)
    #     #             }
    #     #         },
    #     #         "SplitType": "Line",
    #     #         "ContentType": "application/json",
    #     #     },
    #     #     "TransformOutput": {
    #     #         "AssembleWith": "Line",
    #     #         "S3OutputPath": "s3://{0}/{1}".format(s3_bucket, output_s3_key)
    #     #     },
    #     #     "TransformResources": {
    #     #         "InstanceCount": 1,
    #     #         "InstanceType": "ml.m5.large"
    #     #     },
    #     #     "ModelName": model_name
    #     # }
    #
    #     # return {"transform_config": transform_config}
    #     # return json.dumps(transform_config)

    predict = SageMakerTransformOperator(
        task_id='predict',
        config={
            "BatchStrategy": "SingleRecord",
            "TransformJobName": "astro-churn-{0}".format("{{ ts_nodash }}"),
            "TransformInput": {
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": "s3://{0}/{1}/input.jsonl".format(s3_bucket, input_s3_key)
                    }
                },
                "SplitType": "Line",
                "ContentType": "application/json",
            },
            "TransformOutput": {
                "AssembleWith": "Line",
                "S3OutputPath": "s3://{0}/{1}".format(s3_bucket, output_s3_key)
            },
            "TransformResources": {
                "InstanceCount": 1,
                "InstanceType": "ml.m5.large"
            },
            # "ModelName": "{{ ti.xcom_pull(task_ids='get_transform_model_version') }}"
            "ModelName": "sagemaker-soln-churn-js-ds266j-2022-08-03-21-53-47-857"
        }
    )

    # get_transform_model_version() >> predict


dag = sagemaker_batch_inference()
