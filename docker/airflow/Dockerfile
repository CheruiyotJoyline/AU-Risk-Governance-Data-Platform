FROM apache/airflow:3.3.2

# Pinning apache-airflow alongside the extras stops pip from upgrading or
# downgrading Airflow itself when a requirement pulls in a conflicting version.
COPY docker/airflow/requirements.txt /requirements.txt
RUN pip install --no-cache-dir "apache-airflow==${AIRFLOW_VERSION}" -r /requirements.txt
