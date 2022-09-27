# Sagemaker Batch Inference Examples with Airflow

## DAGs
These DAGs are examples on how to use Airflow to orchestrate your ML Ops batch prediction pipelines with Sagemaker.

1. **sagemaker-batch-inference-processing.py** - Runs an end to end data ingest to model publishing pipeline with the following tasks:
    - **process_data (SagemakerProcessingOperator):** Performs ETL transformation to prepare data for prediction.
    - **get_latest_model_version (Python Decorated Task):** Get the latest model version from the Sagemaker Model Registry. Models are named with a distinct naming pattern `<model-name>-v<version number>`
    - **predict (SageMakerTransformOperator):**

## Requirements

### AWS Sagemaker
  - Have a pre-trained, registered, and created model. To do this you can use the Sagemaker notebook provided `include/helper/astronomer-sagemaker-blogpost.ipynb`.
  - Build and push the image used in the SageMakerProcessing task to ECR
    - All code for the image is in `include/helper/processing_job` and you can run the docker commands from that directory
    - Directions on building and pushing https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html
### Airflow
 - Airflow Variables
    - `s3_bucket` - The same bucket used with the provided notebook for inputs and outputs. (The value assigned to the `default_bucket` variable in the notebook)
    - `model_package_group` - The name of the Sagemaker Model Registry Group that you created
    - `role_arn` - Role ARN to be used with the Processing Job task. Usually your Sagemaker execution Role Arn.
 - Airflow Connections
   - `aws_default` - [AWS](https://airflow.apache.org/docs/apache-airflow-providers-amazon/stable/connections/aws.html)
