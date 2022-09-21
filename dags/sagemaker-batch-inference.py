from datetime import datetime, timedelta

import boto3
from airflow.decorators import dag, task, task_group
from airflow.providers.amazon.aws.operators.sagemaker import SageMakerTransformOperator
from airflow.providers.amazon.aws.transfers.s3_to_redshift import S3ToRedshiftOperator
from astro import sql as aql
from astro.files import File
from pandas import DataFrame

output_s3_key = "blogpost/output/"
raw_data = "experiments-demo/validation.csv"
clean_data = "experiments-demo/predict/predict.csv"


@aql.dataframe(columns_names_capitalization='original')
def transform_dataframe(df: DataFrame):
    """This function is meant to simulate any transformation work that would be done on the data like preprocessing,
    feature extraction, etc. In this example we are just performing some simple operations like dropping a column
    because our data is already ready to go for the most part.

    :param df: Pandas dataframe
    :return: Pandas Dataframe
    """

    # Remove label column amd reset index to maker header first row (our data file has no header row)
    # df = df.reset_index().T.reset_index().T
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
def sagemaker_batch_inference():
    """
    This demonstrates a batch inference pipeline using Amazon Sagemaker's Batch Transform.
    """

    @task_group(group_id="etl")
    def etl():
        dataframe = aql.load_file(
            input_file=File(path="s3://{0}/{1}".format("{{ var.value.s3_bucket }}", raw_data))
        )

        no_labels = transform_dataframe(dataframe)

        aql.export_file(
            task_id="save_to_s3",
            input_data=no_labels,
            output_file=File(
                path="s3://{0}/{1}".format("{{ var.value.s3_bucket }}", clean_data),
            ),
            if_exists="replace",
        )

    aql.cleanup()

    @task(task_id='get_latest_model_version')
    def get_latest_model_version(mpg):
        sagemaker_client = boto3.client('sagemaker')
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

    etl() >> get_latest_model_version("{{ var.value.model_package_group }}") >> predict


dag = sagemaker_batch_inference()
