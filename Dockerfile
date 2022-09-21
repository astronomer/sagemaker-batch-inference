FROM quay.io/astronomer/astro-runtime:5.0.8

ENV AIRFLOW__CORE__ENABLE_XCOM_PICKLING=True
ENV AIRFLOW__CORE__XCOM_BACKEND=include.s3_xcom_backend.S3XComBackend