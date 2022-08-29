import json
from datetime import datetime, timedelta
from airflow.decorators import dag, task, task_group
import boto3

from airflow.providers.amazon.aws.operators.sagemaker import SageMakerTransformOperator

from astro import sql as aql
from astro.files import File
from pandas import DataFrame

s3_bucket = 'sagemaker-studio-936535839574-hbsr94yskx5'
output_s3_key = 'blogpost/output/'


@aql.dataframe(columns_names_capitalization='original')
def transform_dataframe(df: DataFrame):
    return df.iloc[:10, 1:]


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
def sagemaker_batch_inference_2():
    """
    This demonstrates a batch inference pipeline using Amazon Sagemaker's Batch Transform.
    """

    @task_group(group_id="etl")
    def etl():
        dataframe = aql.load_file(
            input_file=File(path="s3://sagemaker-us-east-2-936535839574/experiments-demo/validation.csv")
        )

        no_labels = transform_dataframe(dataframe)

        aql.export_file(
            task_id="save_to_s3",
            input_data=no_labels,
            output_file=File(
                path="s3://sagemaker-us-east-2-936535839574/experiments-demo/predict/predict.csv",
            ),
            if_exists="replace",
        )

    aql.cleanup()

    @task(task_id='get_latest_model_version')
    def get_latest_model_version():
        sagemaker_client = boto3.client('sagemaker')
        registered_models = sagemaker_client.list_model_packages(ModelPackageGroupName="lineage-test-1661625924")

        model_version = sagemaker_client.describe_model_package(
            ModelPackageName=registered_models['ModelPackageSummaryList'][0]['ModelPackageArn']
        )

        model_name = "lineage-test-v{}".format(model_version['ModelPackageVersion'])

        return model_name

    predict = SageMakerTransformOperator(
        task_id='predict',
        config={
            "TransformJobName": "lineage-test-job-{0}".format("{{ ts_nodash }}"),
            "TransformInput": {
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": "s3://sagemaker-us-east-2-936535839574/experiments-demo/predict/"
                    }
                },
                "ContentType": "csv",
            },
            "TransformOutput": {
                "S3OutputPath": "s3://{0}/{1}".format(s3_bucket, output_s3_key)
            },
            "TransformResources": {
                "InstanceCount": 1,
                "InstanceType": "ml.m5.xlarge"
            },
            "ModelName": "{{ ti.xcom_pull(task_ids='get_latest_model_version') }}"
        }
    )

    etl() >> get_latest_model_version() >> predict


dag = sagemaker_batch_inference_2()
