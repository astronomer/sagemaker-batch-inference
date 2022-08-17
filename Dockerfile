FROM quay.io/astronomer/astro-runtime:5.0.6

ENV AIRFLOW__CORE__ENABLE_XCOM_PICKLING=True
