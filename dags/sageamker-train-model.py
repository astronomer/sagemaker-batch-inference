"""
A training pipeline using Amazon Sagemaker's Training, Model Registry, Create Model
features.
"""
import logging
from datetime import timedelta

from airflow.decorators import dag, task, task_group
from airflow.providers.amazon.aws.hooks.sagemaker import SageMakerHook
from airflow.providers.amazon.aws.operators.s3 import S3CopyObjectOperator
from airflow.providers.amazon.aws.operators.sagemaker import SageMakerModelOperator
from pendulum import datetime

from astronomer.providers.amazon.aws.operators.sagemaker import SageMakerTrainingOperatorAsync

s3_output_path = "astronomer-demo-dag"

train_data = f"{s3_output_path}/train_data.csv"
validation = f"{s3_output_path}/validation_data.csv"

experiment_name = "astronomer-experiment"
trial_name = "astronomer-trial"
training_job_name = "astronomer-training"


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
def sagemaker_training():
    @task_group
    def get_data():
        """Copy data from public sources to SageMaker S3 buckets."""

        copy_train = S3CopyObjectOperator(
            task_id='copy_train_data',
            source_bucket_name="sagemaker-sample-files",
            source_bucket_key="datasets/tabular/uci_abalone/preprocessed/train.csv",
            dest_bucket_name="{{ var.value.s3_bucket }}",
            dest_bucket_key=train_data
        )

        copy_validation = S3CopyObjectOperator(
            task_id='copy_validation_data',
            source_bucket_name="sagemaker-sample-files",
            source_bucket_key="datasets/tabular/uci_abalone/preprocessed/validation.csv",
            dest_bucket_name="{{ var.value.s3_bucket }}",
            dest_bucket_key=validation
        )

    @task_group
    def train_model():
        @task
        def create_experiment(**kwargs):
            """Create an experiment to track, and if exists already continue with existing one.

            :param kwargs:
            :return: Response from boto3 client request
            :rtype: dict
            """
            sagemaker_client = SageMakerHook().get_conn()

            try:
                response = sagemaker_client.describe_experiment(
                    ExperimentName="{0}-{1}".format(experiment_name, kwargs['ts_nodash']),
                )

                logging.info("Experiment already exists.")

                return response
            except sagemaker_client.exceptions.ResourceNotFound:
                logging.info("Experiment does not exist. Creating new one.")

                response = sagemaker_client.create_experiment(
                    ExperimentName="{0}-{1}".format(experiment_name, kwargs['ts_nodash']),
                )

                return response

        @task
        def create_trial(**kwargs):
            """Create a trial and associate with the experiment

            :param kwargs:
            :return: Response from boto3 client request
            :rtype: dict
            """
            sagemaker_client = SageMakerHook().get_conn()

            try:
                response = sagemaker_client.describe_trial(
                    TrialName="{0}-{1}".format(trial_name, kwargs['ts_nodash']),
                )

                logging.info("Trial already exists.")

                return response

            except sagemaker_client.exceptions.ResourceNotFound:
                logging.info("Trial does not exist. Creating new one.")

                response = sagemaker_client.create_trial(
                    TrialName="{0}-{1}".format(trial_name, kwargs['ts_nodash']),
                    ExperimentName="{0}-{1}".format(experiment_name, kwargs['ts_nodash'])
                )

                return response

        train = SageMakerTrainingOperatorAsync(
            task_id='train',
            config={
                'TrainingJobName': "{0}-{1}".format(training_job_name, "{{ ts_nodash }}"),
                'HyperParameters': {
                    'objective': "reg:squarederror",
                    'num_round': '50',
                    'max_depth': '5',
                    'eta': '0.2',
                    'gamma': '4',
                    'min_child_weight': '6',
                    'subsample': '0.7',
                    'verbosity': '0'
                },
                'AlgorithmSpecification': {
                    'TrainingImage': '257758044811.dkr.ecr.us-east-2.amazonaws.com/sagemaker-xgboost:1.2-2',
                    'TrainingInputMode': 'File',
                },
                'RoleArn': "{{ var.value.role_arn }}",
                'InputDataConfig': [
                    {
                        'ChannelName': 'train',
                        'DataSource': {
                            'S3DataSource': {
                                'S3DataType': 'S3Prefix',
                                'S3Uri': 's3://{0}/{1}'.format("{{ var.value.s3_bucket }}", train_data),
                                'S3DataDistributionType': 'FullyReplicated',
                            },
                        },
                        'ContentType': 'text/csv',
                        'CompressionType': 'None',
                    },
                    {
                        'ChannelName': 'validation',
                        'DataSource': {
                            'S3DataSource': {
                                'S3DataType': 'S3Prefix',
                                'S3Uri': 's3://{0}/{1}'.format("{{ var.value.s3_bucket }}", validation),
                                'S3DataDistributionType': 'FullyReplicated',
                            },
                        },
                        'ContentType': 'text/csv',
                        'CompressionType': 'None',
                    },
                ],
                'OutputDataConfig': {
                    'S3OutputPath': 's3://{0}/{1}'.format("{{ var.value.s3_bucket }}", s3_output_path)
                },
                'ResourceConfig': {
                    'InstanceType': 'ml.m5.large',
                    'InstanceCount': 1,
                    'VolumeSizeInGB': 30,
                },
                'StoppingCondition': {
                    'MaxRuntimeInSeconds': 86400,
                },
                # 'EnableManagedSpotTraining':True|False,
                'ExperimentConfig': {
                    'ExperimentName': "{0}-{1}".format(experiment_name, "{{ ts_nodash }}"),
                    'TrialName': "{0}-{1}".format(trial_name, "{{ ts_nodash }}")
                }
            }
        )

        create_experiment() >> create_trial() >> train

    @task_group
    def register_model():

        @task
        def create_model_package_group(model_package_group):
            """Create a model package group if it doesn't already exist

            :param model_package_group: Name of model package group to create
            :return: Response from boto3 client request
            :rtype: dict
            """
            sagemaker_client = SageMakerHook().get_conn()

            try:
                response = sagemaker_client.create_model_package_group(ModelPackageGroupName=model_package_group)
                return response
            except sagemaker_client.exceptions.ClientError as e:
                logging.info(f'{e}')

        @task
        def register_model_version(model_package_group, model_data_url):
            """Register the new model version created with the train task.

            :param model_package_group: Model Package Group name to registry new version to
            :param model_data_url: Full S3 path to model data artifact
            :return: Response from boto3 client request
            :rtype: dict
            """
            sagemaker_client = SageMakerHook().get_conn()

            response = sagemaker_client.create_model_package(
                ModelPackageGroupName=model_package_group,
                ModelPackageDescription='Brought to you by Astronomer and Sagemaker',
                InferenceSpecification={
                    'Containers': [
                        {
                            'Image': '257758044811.dkr.ecr.us-east-2.amazonaws.com/sagemaker-xgboost:1.2-2',
                            'ModelDataUrl': model_data_url
                        },
                    ],
                    'SupportedTransformInstanceTypes': [
                        'ml.m5.xlarge'
                    ],
                    'SupportedContentTypes': [
                        'text/csv',
                    ],
                    'SupportedResponseMIMETypes': [
                        'text/csv',
                    ]
                },
                ModelApprovalStatus='Approved'
            )

            return response

        create_group = create_model_package_group("{{ var.value.model_package_group }}")
        register_version = register_model_version(
            model_package_group="{{ var.value.model_package_group }}",
            model_data_url=
            "{{ ti.xcom_pull(task_ids='train_model.train')['Training']['ModelArtifacts']['S3ModelArtifacts'] }}"
        )

        create_group >> register_version

    create_model = SageMakerModelOperator(
        task_id='create_model',
        config={
            'ModelName': "{0}-v{1}".format(
                "{{ var.value.model_package_group }}",
                "{{ ti.xcom_pull(task_ids='register_model.register_model_version')['ModelPackageArn'].split('/')[-1] }}"
            ),
            'PrimaryContainer': {
                'ModelPackageName':
                    "{{ ti.xcom_pull(task_ids='register_model.register_model_version')['ModelPackageArn'] }}",
            },
            'ExecutionRoleArn': "{{ var.value.role_arn }}"
        }
    )

    get_data() >> train_model() >> register_model() >> create_model


dag = sagemaker_training()
