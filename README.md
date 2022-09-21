# Databricks Data Science and Machine Learning Examples with Airflow

## DAGs
These DAGs are examples on how to use Airflow to orchestrate your ML Ops batch prediction pipelines with Sagemaker.

1. **sagemaker-batch-inference.py** - Runs an end to end data ingest to model publishing pipeline with the following tasks:
    - **etl (task group):** Performs ETL transformation to prepare data for prediction.
      - **load_file (Astro SDK):** Loads file from S3 which 
      - **transform_dataframe (Astro SDK)**: Prepares data for prediction
      - **save_to_s3 (Astro SDK):** Writes data to S3
    - **get_latest_model_version (Python Decorated Task):** Get the latest model version from the Sagemaker Model Registry. Models are named with a distinct naming pattern `<model-name>-v<version number>`
    - **predict (SageMakerTransformOperator):** 

Note: For this DAG we place AWS credentials as environment variables and not as an Airflow connection. This is to simply avoid putting them in two places, since the API calls to Sagemaker or MLflow that don't use an Airflow operator cannot access those credentials from connections.



## Requirements

### AWS Sagemaker
  - Have a pre-trained, registered, and created model. To do this you can use the Sagemaker notebook provided `include/helper/astronomer-sagemaker-blogpost.ipynb`.

### Airflow
 - Airflow Variables
    - `s3_bucket` - The same bucket used with the provided notebook for inputs and outputs. (The value assigned to the `default_bucket` variable in the notebook)
    - `model_package_group` - The name of the Sagemaker Model Registry Group used
 - AWS environment variables in your .env 
   - AWS_ACCESS_KEY_ID=<your aws access key id>
   - AWS_SECRET_ACCESS_KEY=<your aws secret access key> 
   - AWS_SESSION_TOKEN (If you are using a personal AWS credentials)
   - AWS_DEFAULT_REGION=<your aws region>
   - AIRFLOW__CORE__XCOM_BACKEND=include.s3_xcom_backend.S3XComBackend